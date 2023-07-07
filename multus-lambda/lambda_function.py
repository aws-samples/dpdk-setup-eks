import boto3
import botocore
import os,sys
import ipaddress
import time

from datetime import datetime

ec2_client = boto3.client('ec2')
asg_client = boto3.client('autoscaling')
ec2 = boto3.resource('ec2')
maxFreeIPCOUNT=15
startIndex=3


def lambda_handler(event, context):
    subnetDetails ={}
    tags=[]
    instance_id = event['detail']['EC2InstanceId']
    LifecycleHookName=event['detail']['LifecycleHookName']
    AutoScalingGroupName=event['detail']['AutoScalingGroupName']
    useStaticIPs=False
    log("instance_id:"+str(instance_id) + " ASG:" + str(AutoScalingGroupName) + " LifecycleHookName" + str(LifecycleHookName) )   
    if os.environ['SecGroupIds'] :
        secgroup_ids = os.environ['SecGroupIds'].split(",")
    else:
        log("Empty Environment variable SecGroupIds:"+ os.environ['SecGroupIds'])
        exit (1)  
    if os.environ['SubnetIds'] :
        subnet_ids = os.environ['SubnetIds'].split(",")
    else:
        log("Empty Environment variable SubnetIds:"+ os.environ['SubnetIds'])
        exit (1)     
    if 'useStaticIPs' in os.environ.keys():
        if os.environ['useStaticIPs']=="true":
            useStaticIPs=True
    if 'ENITags' in os.environ.keys():
        tags = os.environ['ENITags'].split(",")

    log("subnet-ids:"+str(subnet_ids)+ "  secgroup-ids:" + str(secgroup_ids) + " useStaticIPs:" + str(useStaticIPs))
    #if only 1 securitygroup is passed then use the same secgroup with all multus, fill the array
    if len(secgroup_ids) != len(subnet_ids):
        if len(secgroup_ids) == 1:
            index=1
            while index < len(subnet_ids) :
                secgroup_ids.append(secgroup_ids[index-1])
                index = index +1
        else:
            log("length of SecGroupIds :"+ len(secgroup_ids)  + "  not same as length of subnets "+ len(subnet_ids) )
            exit (1)               


    if event["detail-type"] == "EC2 Instance-launch Lifecycle Action":
        index = 1
        for x in subnet_ids:
            subnetDetails.clear()
            interface_id=None
            attachment=None
            try: 
                isIPv6=getsubnetData(x,subnetDetails)
                if useStaticIPs == False:
                    interface_id = create_interface(x,secgroup_ids[index-1],isIPv6)
                else:
                    getFreeIPs(x,isIPv6,subnetDetails)       
                    interface_id = create_interface_static(x,secgroup_ids[index-1],isIPv6,subnetDetails)
                if interface_id:
                    log("ENIags values are ")
                    log(tags)
                    log("Start creating ENI tags")
                    ec2_client.create_tags(
                        Resources=[
                              interface_id,
                          ],
                        Tags=[
                                {
                                    'Key': 'node.k8s.amazonaws.com/no_manage',
                                    'Value': 'true'
                            }
                        ]
                    )
                    log("Finished creating the no_manage tag")
                    if len(tags) > 0:
                       add_tags(interface_id,tags,subnetDetails)
                    log("Finished creating the creating tags from the ENITags parameter")
                    attachment = attach_interface(interface_id,instance_id,index)
                index = index+1
            except Exception as e:
                log("Caught unexpected exception: " + str(e))
            if not interface_id:
                complete_lifecycle_action_failure(LifecycleHookName,AutoScalingGroupName,instance_id)
                return
            elif not attachment:
                delete_interface(interface_id)
                complete_lifecycle_action_failure(LifecycleHookName,AutoScalingGroupName,instance_id)
                return 
        complete_lifecycle_action_success(LifecycleHookName,AutoScalingGroupName,instance_id)

    if event["detail-type"] == "EC2 Instance-terminate Lifecycle Action":
        interface_ids = []
        attachment_ids = []

        # -* K8s draining function should be added here -*#

        complete_lifecycle_action_success(LifecycleHookName,AutoScalingGroupName,instance_id)

def getsubnetData(subnet_id,subnetDetails):
    ipv6=False
    try:
        response = ec2_client.describe_subnets(
            SubnetIds=[
                subnet_id,
            ],    
        )
        for i in response['Subnets']:
            subnetDetails['ipv4Cidr']=i['CidrBlock']
            if 'Ipv6CidrBlockAssociationSet' in i.keys():
                for j in  i['Ipv6CidrBlockAssociationSet']:
                    ipv6=True   
                    subnetDetails['ipv6Cidr']=j['Ipv6CidrBlock']
                    log("associated ipv6 CIDR: " + j['Ipv6CidrBlock'])
            if 'Tags' in i.keys():
                for j in i['Tags']:
                    if j['Key'] == "Name":
                        subnetDetails[j['Key']]=j['Value']

    except botocore.exceptions.ClientError as e:
        log("Error describing subnet : {}".format(e.response['Error']))
    return ipv6
def create_interface(subnet_id,sg_id,isIPv6):
    network_interface_id = None
    log("create_interface subnet:" + subnet_id +" secgroup:" + sg_id)

    if subnet_id:
        try:
            if isIPv6 == True:
                network_interface = ec2_client.create_network_interface(Groups=[sg_id],SubnetId=subnet_id, Ipv6AddressCount=1)
            else :
                network_interface = ec2_client.create_network_interface(Groups=[sg_id],SubnetId=subnet_id)
            network_interface_id = network_interface['NetworkInterface']['NetworkInterfaceId']
            log("Created network interface: {}".format(network_interface_id))
        except botocore.exceptions.ClientError as e:
            log("Error creating network interface: {}".format(e.response['Error']))
    return network_interface_id

def create_interface_static(subnet_id,sg_id,isIPv6,subnetDetails):
    network_interface_id = None
    log("create_interface_static subnet:" + subnet_id +" secgroup:" + sg_id)
    if subnet_id:
        for ip in subnetDetails['freeIpv4s']:
            try:
                network_interface = ec2_client.create_network_interface(Groups=[sg_id],SubnetId=subnet_id,PrivateIpAddress=ip)
                network_interface_id = network_interface['NetworkInterface']['NetworkInterfaceId']
                log("Created network interface:  "+ network_interface_id + " ipv4 IP: "+ ip )
                break                
            except botocore.exceptions.ClientError as e:
                log("Error creating network interface with ip: " + ip + " Error:" + str(e.response['Error']))
        if isIPv6 == True :
            if network_interface_id == None:
                pass
            else:    
                if 'freeIpv6s' in subnetDetails.keys():
                    for ip in subnetDetails['freeIpv6s']:
                        try:
                            resp = ec2_client.assign_ipv6_addresses(Ipv6Addresses=[ip],NetworkInterfaceId=network_interface_id)
                            log("Assigned Ipv6 Address on ENI: "+ network_interface_id + " with ipv6 IP: "+ ip )
                            break
                        except botocore.exceptions.ClientError as e:
                             log("Error creating network interface with ip: " + ip + " Error:" + str(e.response['Error']))
    return network_interface_id

def attach_interface(network_interface_id, instance_id, index):
    attachment = None
    log("attach_interface instance:" + instance_id +" eni:" + network_interface_id + " eni-index: " + str(index))

    if network_interface_id and instance_id:
        try:
            attach_interface = ec2_client.attach_network_interface(
                NetworkInterfaceId=network_interface_id,
                InstanceId=instance_id,
                DeviceIndex=index
            )
            if 'AttachmentId' in attach_interface.keys():
                attachment = attach_interface['AttachmentId']
                log("Created network attachment: {}".format(attachment))
            else:
                 log("Network attachment creation returned NULLL")                  
        except botocore.exceptions.ClientError as e:
            log("Error attaching network interface: {}".format(e.response['Error']))

    network_interface = ec2.NetworkInterface(network_interface_id)

    #modify_attribute doesn't allow multiple parameter change at once..
    network_interface.modify_attribute(
        Attachment={
            'AttachmentId': attachment,
            'DeleteOnTermination': True
        },
    )

    return attachment

def add_tags(network_interface_id,tags,subnetDetails):
    network_interface = ec2.NetworkInterface(network_interface_id)
    for tag in tags:
        x=tag.split('=')
        if len(x) > 1:
            network_interface.create_tags(
                Tags=[{'Key': x[0],'Value': x[1]} ]
            )
    if 'Name' in subnetDetails.keys():
        network_interface.create_tags(
                    Tags=[{'Key': 'Name','Value': subnetDetails['Name'] } ]
                )         
    if 'ipv4Cidr' in subnetDetails.keys():
        network_interface.create_tags(
                    Tags=[{'Key': 'ipv4Cidr','Value': subnetDetails['ipv4Cidr'] } ]
                )   
    if 'ipv6Cidr' in subnetDetails.keys():
        network_interface.create_tags(
                    Tags=[{'Key': 'ipv6Cidr','Value': subnetDetails['ipv6Cidr'] } ]
                )                           
def delete_interface(network_interface_id):
    log("delete_interface eni:" + network_interface_id)

    try:
        ec2_client.delete_network_interface(
            NetworkInterfaceId=network_interface_id
        )
        log("Deleted network interface: {}".format(network_interface_id))
        return True

    except botocore.exceptions.ClientError as e:
        log("Error deleting interface {}: {}".format(network_interface_id,e.response['Error']))


def complete_lifecycle_action_success(hookname,groupname,instance_id):
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=hookname,
            AutoScalingGroupName=groupname,
            InstanceId=instance_id,
            LifecycleActionResult='CONTINUE'
        )
        log("Lifecycle hook CONTINUEd for: {}".format(instance_id))
    except botocore.exceptions.ClientError as e:
            log("Error completing life cycle hook for instance {}: {}".format(instance_id, e.response['Error']))
            log('{"Error": "1"}')

def complete_lifecycle_action_failure(hookname,groupname,instance_id):
    try:
        asg_client.complete_lifecycle_action(
            LifecycleHookName=hookname,
            AutoScalingGroupName=groupname,
            InstanceId=instance_id,
            LifecycleActionResult='ABANDON'
        )
        log("Lifecycle hook ABANDONed for: {}".format(instance_id))
    except botocore.exceptions.ClientError as e:
            log("Error completing life cycle hook for instance {}: {}".format(instance_id, e.response['Error']))
            log('{"Error": "1"}')

def get_used_ip_list(subnet_id,subnetDetails):
    usedIpv4s=[]
    usedIpv6s=[]
    try:
        resp = ec2_client.describe_network_interfaces(
                     Filters=[ {'Name': 'subnet-id',  'Values': [subnet_id] } ]
            ) 
        for en in resp['NetworkInterfaces']: 
            eni = en['NetworkInterfaceId']  
            for ip in en['PrivateIpAddresses'] : 
                usedIpv4s.append(ip['PrivateIpAddress'])
            for ip in en['Ipv6Addresses'] : 
                usedIpv6s.append(ip['Ipv6Address'])
    except botocore.exceptions.ClientError as e:
        log("Error describing subnet : {}".format(e.response['Error']))  
    subnetDetails['usedIpv4s'] = usedIpv4s
    log("usedIpv4s: " + str(subnetDetails['usedIpv4s']))

    if len(usedIpv6s) >0 : 
        subnetDetails["usedIpv6s"]=usedIpv6s
        log("usedIpv6s: " + str(subnetDetails['usedIpv6s']))


def getFreeIPs(subnet_id,isIPv6, subnetDetails):
    get_used_ip_list(subnet_id,subnetDetails)
    net = ipaddress.IPv4Network(subnetDetails['ipv4Cidr'])
    subnetDetails['freeIpv4s']=[]
    subnetDetails['freeIpv6s']=[]

    count = 0
    for ip in net.hosts():
        count = count +1
        ipFree=False
        if count <= startIndex:
            continue 
        if  'usedIpv4s' in subnetDetails.keys():  
            if str(ip) not in subnetDetails['usedIpv4s']:
                ipFree = True
        else:
            ipFree= True
        if ipFree == True:          
            subnetDetails['freeIpv4s'].append(str(ip))
        if len (subnetDetails['freeIpv4s']) >= maxFreeIPCOUNT:
            log("Free Ips: " + str(subnetDetails['freeIpv4s']))
            break
    if isIPv6== True:   
        if 'ipv6Cidr' in subnetDetails.keys():
            net = ipaddress.IPv6Network(subnetDetails['ipv6Cidr'])
            count = 0         
            for ip in net.hosts():
                ipFree=False
                count = count +1
                if count <= startIndex:
                    continue 
                if  'usedIpv6s' in subnetDetails.keys():  
                    if str(ip) not in subnetDetails['usedIpv6s']:
                        ipFree = True
                else:
                    ipFree= True
                if ipFree == True:          
                    subnetDetails['freeIpv6s'].append(str(ip))
                if len (subnetDetails['freeIpv6s']) >= maxFreeIPCOUNT:
                    log("Free Ips: " + str(subnetDetails['freeIpv6s']))
                    break
def log(error):
    print('{}Z {}'.format(datetime.utcnow().isoformat(), error))