#!/bin/bash
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>>/var/log/userdata-sriov-log.out 2>&1
echo "#####################################################"
echo "Echo from sriov-init.sh."
echo "#####################################################"

if ! [[ -f "/var/tmp/finish_sriov_initialization" ]]; then

/bin/aws s3api get-object --bucket S3BucketName --key get-vfio-with-wc.sh ./get-vfio-with-wc.sh

chmod +x get-vfio-with-wc.sh

mkdir patches;cd patches

/bin/aws s3api get-object --bucket S3BucketName --key linux-4.10-vfio-wc.patch ./linux-4.10-vfio-wc.patch
/bin/aws s3api get-object --bucket S3BucketName --key linux-5.8-vfio-wc.patch ./linux-5.8-vfio-wc.patch
cd ..
./get-vfio-with-wc.sh

systemctl enable config-sriov.service

echo "Initialization completed..."
touch /var/tmp/finish_sriov_initialization

else
  echo "Initialization already completed, skipping ..."
fi