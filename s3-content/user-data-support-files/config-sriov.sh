#!/bin/bash
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>>/var/log/userdata-sriov-log.out 2>&1
echo "#####################################################"
echo "Echo from config-sriov.sh."
echo "#####################################################"
modprobe vfio_pci
echo 1 > /sys/module/vfio/parameters/enable_unsafe_noiommu_mode
for intf in eth{SriovStartingInterface..subnetCount}; do
  pci_id=`ls -l /sys/class/net/"$intf" | grep device | cut -d '/' -f 9`
  echo "$pci_id"
  /opt/dpdk/dpdk-devbind.py -u "$pci_id"
  /opt/dpdk/dpdk-devbind.py -b vfio-pci "$pci_id"
done