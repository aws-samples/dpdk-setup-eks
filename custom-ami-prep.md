## Custom DPDK AMI Creation

To create a custom AMI, following steps are required:

1.) Create an EC2 instance from an EKS Optimized AMI image. As an example to get the optimized AMI image for EKS 1.23 in us-west-2 region, the following command can be used:

```
aws ssm get-parameter --name /aws/service/eks/optimized-ami/1.23/amazon-linux-2/recommended/image_id --region us-west-2 --query "Parameter.Value" --output text

ami-0996383fb9a4fd26b
```

This will give the latest version for the EKS AMI 1.23 release.

The AMI id that is given from the command can now be used to provision an EC2 instance.

```
aws --region us-west-2 ec2 run-instances \
    --image-id ami-0996383fb9a4fd26b \
    --count 1 \
    --instance-type t3.medium \
    --key-name local-key \
    --security-group-ids sg-0b5078d10994b91c7 \
    --subnet-id subnet-01dfeb4802507fa16 \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sdf\",\"Ebs\":{\"VolumeSize\":50,\"DeleteOnTermination\":false}}]" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=dpdk-image}]'
```



After the EC2 instance is created, open a terminal session via SSH or SSM and run the following steps to install the required DPDK software and configure the kernel parameters:

2.) Update and install required packages

```
sudo yum -y update
sudo yum -y install net-tools pciutils numactl-devel libhugetlbfs-utils libpcap-devel kernel kernel-devel kernel-headers git
```

3.) Reboot the instance: `sudo reboot`

4.) Install AWS DPDK patches

```
git clone https://github.com/amzn/amzn-drivers.git

wget https://raw.githubusercontent.com/amzn/amzn-drivers/master/userspace/dpdk/enav2-vfio-patch/get-vfio-with-wc.sh
chmod +x get-vfio-with-wc.sh
mkdir patches;cd patches
wget https://raw.githubusercontent.com/amzn/amzn-drivers/master/userspace/dpdk/enav2-vfio-patch/patches/linux-4.10-vfio-wc.patch
wget https://raw.githubusercontent.com/amzn/amzn-drivers/master/userspace/dpdk/enav2-vfio-patch/patches/linux-5.8-vfio-wc.patch

cd ..
sudo ./get-vfio-with-wc.sh
```

5.) Download dpdk scripts (Change DPDK_S3_BUCKET_NAME to the S3 bucket that contains the dpdk scripts)

```
sudo mkdir -p /opt/dpdk/
sudo /bin/aws s3api get-object --bucket DPDK_S3_BUCKET_NAME --key dpdk-devbind.py /opt/dpdk/dpdk-devbind.py
sudo chmod +x /opt/dpdk/dpdk-devbind.py

sudo /bin/aws s3api get-object --bucket DPDK_S3_BUCKET_NAME --key config-sriov.service /usr/lib/systemd/system/config-sriov.service
sudo /bin/aws s3api get-object --bucket DPDK_S3_BUCKET_NAME --key dpdk-resource-builder.py /opt/dpdk/dpdk-resource-builder.py
sudo /bin/aws s3api get-object --bucket DPDK_S3_BUCKET_NAME --key config-sriov.sh /opt/dpdk/config-sriov.sh
```

6.) Add VFIO-PCI driver to start at boot time

```
sudo sh -c 'echo "vfio" >> /etc/modules-load.d/dpdk.conf'
sudo sh -c 'echo "vfio-pci" >> /etc/modules-load.d/dpdk.conf'
sudo chmod 644 /etc/modules-load.d/dpdk.conf
sudo sh -c 'echo "options vfio enable_unsafe_noiommu_mode=1" > /etc/modprobe.d/dpdk.conf'
sudo chmod 644 /etc/modprobe.d/dpdk.conf
```

You can add other steps that may be required for the specific CNF.

7.) Reboot the instance: `sudo reboot`

8.) The AMI image can be created off the EC2 instance, sample command to create an EC2 AMI image from an existing EC2 instance. Replace INSTANCE_ID with the EC2 instance

```
aws ec2 create-image --instance-id INSTANCE_ID --name "dpdk_custom_ami" --description "An AMI for DPDK"
```

The custom AMI can be used to create the required EKS worker node.