# Automate Packet Acceleration configuration using DPDK on Amazon EKS

This repo shows how to deploy a sample DPDK CNF on AWS EKS cluster.

***Note - You will be required to build the dpdk-aws-ipmgt container image and push to your ECR. Details on how to do this can be found in the dpdk-cnf-deployment/container-building folder.***

## Overview

SRIOV is supported by the [Elastic Network Adapter](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/enhanced-networking-ena.html) (ENA) on the Amazon EC2 Linux instances. All current Amazon EC2 instances except T2 support ENA drivers by default. Amazon Linux 2 based [Amazon Machine Images](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/AMIs.html) (AMI) including EKS optimized AMIs have ENA drivers enabled by default. Moreover, many other popular linux based AMIs from other vendors also support the ENA driver by default.  You can refer to [documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/enhanced-networking-ena.html) for further steps. In this post we will be using EKS optimized Amazon Linux 2 AMI.

Now that you have SRIOV enabled AMI and instance, we would walk you through the automation steps to enable DPDK on your EKS worker nodes.

### DPDK Configuration

Your DPDK enabled workloads, have the DPDK library to use them, though the underlying worker nodes to configure and automate following using the [Amazon EC2 userdata](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html)

1. Install linux libraries, ENA compatible drivers and patches needed for DPDK & huge pages setup
2. Linux sysctl configuration as per the workload requirement
3. Configure any hugepages configuration and setup CPUAffinity for system based on your Numa configuration
4. Enabling secondary interfaces used by your workloads 
5. Bind your secondary interfaces with DPDK drivers, such as vfio-pci driver 
6. Prepare the config file for [SRIOV-DP plugin](https://github.com/k8snetworkplumbingwg/sriov-network-device-plugin), which maps the interface’s pciAddress to a resource name

Based on your requirement you can chose either of the two options mentioned below to prepare your worker nodes.

#### Option 1: Pre-built AMI with DPDK Setup

In this option you would prepare the custom built AMI with all required patches, configuration and operating system level setups. You can use the EKS Optimized Amazon Linux AMI or any other ENA driver enabled linux AMI as base AMI and create an EC2 instance. Once the node is up, you can perform step 1-3 mentioned in DPDK Configuration section with [user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html) of your Launch template. After the installation & configuration steps are completed, you can prepare a new AMI from the root disk (EBS volume) and use it as an AMI for your worker nodes requiring DPDK. 

You can find the detailed steps that are required for creating the custom AMI at [custom-ami-build-steps](./custom-ami-prep.md)

After creating the custom AMI you can proceed to deploy the cloud formation template that will create the worker-nodes, steps are provided at the [worker-node creation step](#create-the-worker-node-with-dpdk-interfaces).

#### Option 2: On-Demand DPDK installation and Configuration

In this option, you take the latest EKS Optimized Amazon Linux AMI or any other ENA driver enabled linux AMI and deploy your worker nodes. You automate all the necessary steps as mentioned in above ‘DPDK Configuration’ section with [user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html) of your Launch template. 
You can store your packages, patches, helper & configuration scripts in a private [Amazon S3](https://aws.amazon.com/s3/) bucket. At the time instantiation EC2 node will download these files from the S3 bucket and utilizes it for patch installation, DPDK setup, and system configuration. It also gives you flexibility to decide on number of interfaces needed to be DPDK bound and build it with the planned resource names used by your workloads via SRIOV-DP plugin.

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

From the above, the interfaces that are have **_drv=vfio-pci_** are the interfaces that have been bound to the vfio-pci DPDK driver.

### AWS-Auth Configmap For The NodeGroup

After the cloud formation for the worker node has completed, there is need to add the instance role of the worker node to the EKS cluster aws-auth configmap, this is needed for the worker node to join the EKS cluster. Use the following command syntax to add the instance role (you can get the instance role arn from the output section of the cloud formation stack)



```
cat <<EOF | kubectl apply -f-
apiVersion: v1
kind: ConfigMap
metadata:
  name: aws-auth
  namespace: kube-system
data:
  mapRoles: |
    - rolearn: arn:aws:iam::xxxxxxxx:role/NG-workers-NodeInstanceRole-XXXXX
      username: system:node:{{EC2PrivateDNSName}}
      groups:
        - system:bootstrappers
        - system:nodes
EOF 
```

### SRIOV Device Plugin Setup

The sriov device plugin daemonset manifest can be found at ***dpdk-cnf-deployment/sriovdp-ds.yaml*** One major thing to note is that the sriov-device plugin configuration is not provided as a config-map instead it is mounted as a HostPath within the daemonset manifest:

```
      - hostPath:
          path: /etc/pcidp/config.json
          type: ""
        name: config-volume
```

***/etc/pcidp/config.json*** will be created during the cloud formation setup (via the /opt/dpdk/dpdk-resource-builder.py script section of the userdata) for the NodeGroup.

### Deploy Sample Application to Validate the setup

The sample DPDK CNF that will be used is  VPP (Vector Packet Processor), VPP is a popular packet switching software that has support for using DPDK for the packet processing. An helm chart has been created with the necessary parameters to deploy a sample VPP POD. The status of the VPP pod deployment after installation is given below



- Below shows the environment variables that confirms that the sriov-device plugin has injected the DPDK interfaces using the respective PCI Interface Addresses

```
kubectl -n dpdk exec -ti deploy/core-vpp-dpdk printenv | grep PCI

PCIDEVICE_INTEL_COM_INTEL_SRIOV_NETDEVICE_3=0000:00:08.0
PCIDEVICE_INTEL_COM_INTEL_SRIOV_NETDEVICE_1=0000:00:06.0
PCIDEVICE_INTEL_COM_INTEL_SRIOV_NETDEVICE_2=0000:00:07.0
```

- Status of the DPDK within the VPP shell:

```
vpp# show run
.
.
.
Thread 1 vpp_wk_0 (lcore 63)
Time 48.9, 10 sec internal node vector rate 0.00 loops/sec 6188602.79
  vector rates in 6.1404e-2, out 0.0000e0, drop 6.1404e-2, punt 0.0000e0
             Name                 State         Calls          Vectors        Suspends         Clocks       Vectors/Call
arp-input                        active                  1               3               0          3.24e3            3.00
arp-reply                        active                  1               3               0          1.51e4            3.00
dpdk-input                       polling         297451577               3               0         2.42e10            0.00
drop                             active                  1               3               0          1.78e3            3.00
error-drop                       active                  1               3               0          1.59e3            3.00
ethernet-input                   active                  3               3               0          2.35e4            1.00
unix-epoll-input                 polling            290228               0               0          2.76e3            0.00

vpp# show dpdk version
DPDK Version:             DPDK 22.07.0
DPDK EAL init args:       --in-memory --no-telemetry --file-prefix vpp -a 0000:00:06.0 -a 0000:00:07.0 -a 0000:00:08.0
```

The procedure to deploy the VPP CNF can be found at ***dpdk-cnf-deployment*** folder of the Git repo