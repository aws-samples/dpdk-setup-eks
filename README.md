# Automate Packet Acceleration configuration using DPDK on Amazon EKS

This repo contains sample Cloudformation templates and DPDK based CNF helm chart that can be used to automate the process of creating DPDK packet acceleration on an EKS cluster. 

For more details on the implementation steps kindly check the blog post at <link to the blog post>

***Note - You will be required to build the dpdk-aws-ipmgt container image and push to your ECR. Details on how to do this can be found in the dpdk-cnf-deployment/container-building folder.***

#### Pre-requisites

The sample CFN (CloudFormation) template that is included in the blog's git repo is to create the EKS node-group only, the following resources needs to be created beforehand and the values used as part of the variables that will be used for the NodeGroup CFN stack creation.

* **VPC ID**
* **WokerNode Primary Interface (eth0) Subnet ID:** This is the subnet that the worker node EC2 instances will be created (this is will be used for the Kubernetes primary interface i.e. aws-vpc-cni).
* **Multus Subnets Groups ID**: The list of multus subnets that will be used to create the DPDK interfaces.
* **DPDK S3 Bucket:** This is where the DPDK scripts will be called during the userdata initialization. The scripts can be found at ***s3-content/user-data-support-files*** folder that is included in the git repo.
* **Multus S3 Bucket:** This is where the zipped Multus Lambda function code will be stored. You can find the zipped file in ***multus-lambda*** folder that is included in the git repo.
* **EKS Cluster:** The values that is required is the EKS Cluster Name.
* **EKS Security Group:** The security group ID that was created alongside with EKS cluster.

#### Option 1: Pre-built AMI with DPDK Setup

In this option you would prepare the custom built AMI with all required patches, configuration and operating system level setups. You can use the EKS Optimized Amazon Linux AMI or any other ENA driver enabled linux AMI as base AMI and create an EC2 instance. Once the node is up, you can install DPDK driver patches. After the installation & configuration steps are completed, you can prepare a new AMI from the root disk (EBS volume) and use it as an AMI for your worker nodes requiring DPDK. 

You can find the detailed steps that are required for creating the custom AMI at [custom-ami-build-steps](./custom-ami-prep.md)

After creating the custom AMI you can proceed to deploy the cloud formation template that will create the worker-nodes, steps are provided at the [worker-node creation step](#create-the-worker-node-with-dpdk-interfaces). 

#### Option 2: On-Demand DPDK installation and Configuration

In this option, you take the latest EKS Optimized Amazon Linux AMI or any other ENA driver enabled linux AMI and deploy your worker nodes. You can automate all the necessary steps as mentioned in above ‘DPDK Configuration’ section with [user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html) of your Launch template. 
You can store your packages, patches, helper & configuration scripts in a private Amazon S3 bucket. At the time of instantiation, EC2 node will download these files from the S3 bucket and utilizes it for patch installation, DPDK setup, and system configuration. It also gives you flexibility to decide on number of interfaces needed to be DPDK bound and build it with the planned resource names used by your workloads via SRIOV-DP plugin.

For this option, there is no need to do any prep work, all the DPDK installation processes are carried out within the cloud formation stack via the user-data script section, the cloud formation step can be found at the  [worker-node creation step](#create-the-worker-node-with-dpdk-interfaces)

#### Create The Worker Node With DPDK Interfaces

Please use the sample [AWS Cloud Formation](./CFN-Templates/eks-dpdk-nodegroup-v1.yaml) template to create your EKS nodegroup for your DPDK enabled workloads. 

Select Create stack, with new resources(standard).

Click *Template is ready" (default), "Upload a template file", "Choose file". Select the cloudformation file that you have downloaded from this GitHub.

```
    Stack name -> ng1 (your stack name)
    ClusterName -> eks-multus-cluster (your own eks cluster name)
    ClusterControlPlaneSecurityGroup -> "eks-multus-cluster-EksControlSecurityGroup-xxxx" (your own cluster security group)
    NodeGroupName -> ng1 (your node group name)
    AutoScalingGroup Min/Desired/MaxSize -> 1/2/3 (your nodegroup size min/desired/max size)
    NodeInstanceType -> select EC2 flavor, based on the requirement (or choose default)
    NodeImageIdSSMParam --> EKS optimized linux2 AMI release (default 1.23, change the release value, if needed)
    NodeImageId --> (if using custome AMI then use AMIID, this option will override NodeImageIdSSMParam)
    NodeVolumeSize --> configure Root Volume size (default 50 gb)
    KeyName -> ee-default-keypair (or any ssh key you have)
    BootstrapArguments -> configure your k8 node labels, (leave default if not sure)
    useIPsFromStartOfSubnet -> use true (to use option 1 mentioned above) or false (to use option 2 i.e. cidr reservation)
    VpcId -> vpc-eks-multus-cluster (that you created)
    Subnets -> privateAz1-eks-multus-cluster (this is for main primary K8s networking network)
    MultusSubnets -> multus1Az1 and Multus2Az1 (subnets are attached in same order as provided, so multus1Az1 as eth1 and Multus2Az1 as eth2 )
    MultusSecurityGroups -> multus-Sg-eks-multus-cluster
    LambdaS3Bucket -> the s3 bucket name where lambda function zip file is stored
    LambdaS3Key -> lambda_function.zip
    InterfaceTags --> (optional , leave it blank or put a key-value pair as Tags on the i/f)
    DPDKFilesS3BucketName --> the s3 bucket name where DPDK and supported scripts are stored
    hugepagesz --> The desired huge page size
    Defaulthugepagesz --> The desired default huge page size
    NumOfHugePages --> Number of huge pages 
    SriovStartingInterface --> The starting interface number you would like to use for DPDK. DPDK binding starts from this interface and ends at the last multus interface. if you need to use any non-dpdk interface using ipvlan, then start SriovStartingInterface after those interface order.   
```

Next, check "I acknowledge...", and then Next.

Note: The same cloud formation template is used for both Pre-built and On-Demand configuration

#### Validation of DPDK interface setup

To confirm that the DPDK driver is loaded, use the below step

```
[ssm-user@ip-192-168-2-71 bin]$ lsmod | grep vfio
vfio_pci               65536  3
vfio_virqfd            16384  1 vfio_pci
vfio_iommu_type1       32768  0
vfio                   36864  10 vfio_iommu_type1,vfio_pci
irqbypass              16384  7 vfio_pci
```

Execute below command to verify if your DPDK interfaces are bound

```
[ssm-user@ip-192-168-2-71 bin]$ /opt/dpdk/dpdk-devbind.py -s

Network devices using DPDK-compatible driver
============================================
0000:00:06.0 'Elastic Network Adapter (ENA) ec20' drv=vfio-pci unused=ena
0000:00:07.0 'Elastic Network Adapter (ENA) ec20' drv=vfio-pci unused=ena
0000:00:08.0 'Elastic Network Adapter (ENA) ec20' drv=vfio-pci unused=ena

Network devices using kernel driver
===================================
0000:00:05.0 'Elastic Network Adapter (ENA) ec20' if=eth0 drv=ena unused=vfio-pci *Active*
0000:00:09.0 'Elastic Network Adapter (ENA) ec20' if=eth1 drv=ena unused=vfio-pci

No 'Baseband' devices detected
==============================

No 'Crypto' devices detected
============================

No 'DMA' devices detected
=========================

No 'Eventdev' devices detected
==============================

No 'Mempool' devices detected
=============================

No 'Compress' devices detected
==============================

No 'Misc (rawdev)' devices detected
===================================

No 'Regex' devices detected
===========================
```

## Clean up 
* Delete the private DPDK AMI from EC2 console. 
* Go to CloudFormation and Delete the EKSNodegroup stack.
  
## Security

See [CONTRIBUTING](https://github.com/aws-samples/dpdk-setup-eks/blob/main/CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
