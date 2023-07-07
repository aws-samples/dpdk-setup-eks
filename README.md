# Automate Packet Acceleration configuration using DPDK on Amazon EKS

This repo shows how to deploy a sample DPDK CNF on AWS EKS cluster.

***N.B - You will be required to build the dpdk-aws-ipmgt container image and push to your ECR. Details on how to do this can be found in the dpdk-cnf-deployment/container-building folder ***

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

For your workload EKS worker node preparation, you can use this pre-built AMI and perform the steps 4-6 mentioned in DPDK Configuration section. As these steps just being configuration steps, user data execution finishes fast. It still gives you flexibility to decide on number of interfaces needed to be DPDK bound and build it with the planned resource names used by your workloads via SRIOV-DP plugin.

Advantage of this approach is that, faster bringup as most of the time taking installation is completed  in advance.Pre-downloaded packages, no need to manage the patches on S3 buckets. Disadvantage of this approach is  sharing the pre-built AMI across multiple accounts, keeping uptodate with security patches on the base AMI,, For different requirements, such as hugepage configuration, dpdk version, you would have to manage multiple unique pre-built AMIs.

The steps to build a sample custom AMI has been provided in the ***custom-ami-prep.md*** file that is included in the Git repo that was created for this blog post.

#### Option 2: On-Demand DPDK installation and Configuration

In this option, you take the latest EKS Optimized Amazon Linux AMI or any other ENA driver enabled linux AMI and deploy your worker nodes. You automate all the necessary steps as mentioned in above ‘DPDK Configuration’ section with [user data](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html) of your Launch template. 
You can store your packages, patches, helper & configuration scripts in a private [Amazon S3](https://aws.amazon.com/s3/) bucket. At the time instantiation EC2 node will download these files from the S3 bucket and utilizes it for patch installation, DPDK setup, and system configuration. It also gives you flexibility to decide on number of interfaces needed to be DPDK bound and build it with the planned resource names used by your workloads via SRIOV-DP plugin.

Advantage of this approach is, you dont need custom built AMIs and your system is getting prepared dynamically with latest base AMI, for each of the different usecase. You dont have to manage multiple custom built AMIs,  share across multiple accounts, keeping uptodate with security patches on the base AMI, maintaining multiple versions of the AMI. Different requirements, such as hugepage configuration, dpdk version is handled via automation dynamically.  Disadvantage of this approach is a slight increased bingup time compared to custom-built AMI, as patches are getting installed at bringup time.   

Refer to <<git page>> for detailed steps, configuration and a sample [AWS Cloud Formation](https://aws.amazon.com/cloudformation/) template to create your EKS nodegroup for your DPDK enabled workloads. 



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

The sriov device plugin daemonset manifest can be found at ***dpdk-cnf-deployment/sriovdp-ds.yaml .\*** One major thing to note is that the sriov-device plugin configuration is not provided as a config-map instead it is mounted as a HostPath within the daemonset manifest:

```
      - hostPath:
          path: /etc/pcidp/config.json
          type: ""
        name: config-volume
```

***/etc/pcidp/config.json\*** will be created during the cloud formation setup (via the /opt/dpdk/dpdk-resource-builder.py script section of the userdata) for the NodeGroup.

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
