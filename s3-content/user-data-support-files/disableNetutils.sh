#!/bin/bash
#####################################################
# Disable NetUtils Logic - START
#####################################################
DATE=$(date)
LOGFILE=/var/log/disableNetutils.log
ETH1=/etc/sysconfig/network-scripts/ifcfg-eth1
ETH1r=/etc/sysconfig/network-scripts/route-eth1
ETH2=/etc/sysconfig/network-scripts/ifcfg-eth2
ETH2r=/etc/sysconfig/network-scripts/route-eth2
REBOOT_DONE=/var/tmp/reboot_done
let totalTime=0

if yum list installed ec2-net-utils >/dev/null 2>&1; then
    echo "$DATE ec2-net-utils package is already installed, moving ahead\\n" >> $LOGFILE
else
    echo "$DATE Installing ec2-net-utils package\\n" >> $LOGFILE
    yum install ec2-net-utils -y
    sleep 5
    systemctl restart network
fi

echo "$DATE Disabling the ec2-net-util interface automation... \\n" >> $LOGFILE
while true
do
    if [ -f $ETH1 ] && [ -z $ETH1_WORK ]; then
        sed -i 's/BOOTPROTO=dhcp/BOOTPROTO=none/g' $ETH1
        sed -i 's/EC2SYNC=yes/EC2SYNC=no/g' $ETH1
        sed -i 's/MAINROUTETABLE=yes/MAINROUTETABLE=no/g' $ETH1
        ETH1_WORK=true
        echo "$DATE Replaced for ifcfg-eth1\\n" >> $LOGFILE
        cat $ETH1 >> $LOGFILE
        touch $ETH1r
    fi
    if [ -f $ETH2 ] && [ -z $ETH2_WORK ]; then
        sed -i 's/EC2SYNC=yes/EC2SYNC=no/g' $ETH2
        sed -i 's/MAINROUTETABLE=yes/MAINROUTETABLE=no/g' $ETH2
        ETH2_WORK=true
        echo "$DATE Replaced for ifcfg-eth2\\n" >> $LOGFILE
        cat $ETH2 >> $LOGFILE
        touch $ETH2r
    fi
    if [ -f $ETH1r ] && [ -z $ETH1r_WORK ]; then
        cat /dev/null > $ETH1r
        ETH1r_WORK=true
        echo "$DATE Replaced for route-eth1\\n" >> $LOGFILE
        cat $ETH1r >> $LOGFILE
    fi
    if [ -f $ETH2r ] && [ -z $ETH2r_WORK ]; then
        cat /dev/null > $ETH2r
        ETH2r_WORK=true
        echo "$DATE Replaced for route-eth2\\n" >> $LOGFILE
        cat $ETH2r >> $LOGFILE
    fi
    let totalTime=$totalTime+5

    if [ $ETH1_WORK ] && [ $ETH2_WORK ] && [ $ETH1r_WORK ] && [ $ETH2r_WORK ]; then
        echo "$DATE All replacements completed.\\n" >> $LOGFILE
        break
    elif [ $totalTime -gt 300 ]; then
        echo "$DATE Could not find all files after 5 minutes\\n" >> $LOGFILE
        if [ ! -f $REBOOT_DONE ]; then
            echo "$DATE Rebooting to initiate EC2_Net_Utils automation\\n" >> $LOGFILE
            touch $REBOOT_DONE
            reboot
        else
            echo "$DATE This automation has rebooted once, please check if ifcfg-eth* and route-eth* files are created for all eth devices\\n" >> $LOGFILE
            exit 1
        fi
        
    fi
    sleep 5
done
#####################################################
# Disable NetUtils Logic - END
#####################################################