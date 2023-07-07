#!/bin/bash
#Script written to assign specific IP for a PCI Address of an ENI

# sample environment template:
# Aws_PCI_0000:00:06.0={10.0.4.10,10.0.4.11}
# Aws_PCI_0000:00:07.0={10.0.6.10,10.0.6.11}
# Entries must be placed in /etc/pci-address-ip-mapping

function attachIPtoENI(){
    region=$(curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | jq -r .region)
    eniAttachmentID=$(aws --region ${region} ec2 describe-network-interfaces --filters Name=mac-address,Values=${1} | jq -r .NetworkInterfaces[].NetworkInterfaceId)
    echo "Proceeding to assign IP ${2} to ENI ${eniAttachmentID}"
    aws --region ${region} ec2 assign-private-ip-addresses --network-interface-id ${eniAttachmentID} --private-ip-addresses ${2} --allow-reassignment
}


for i in $(grep Aws_PCI /etc/pci-address-ip-mapping)
do
  pciAddress=$(echo ${i} | cut -d '=' -f1 | cut -d '_' -f3)
  macAddress=$(dmesg | grep mac | grep ${pciAddress} | awk '{print $NF}')
  for x in $(echo ${i} | cut -d '=' -f2 | tr ',' ' ' |tr -d \"{})
  do
    echo "Attaching IP address ${x} to the ENI that has Mac Address ${macAddress}"
    attachIPtoENI ${macAddress} ${x}
  done
done