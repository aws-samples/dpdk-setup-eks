#!/bin/bash
#####################################################
# Name: Node Join Detector Script
# Creator: aviragz@amazon.com (Avinash Raghavendra)
# Version 1.0
#####################################################
#Region=$Region
#StackName=$StackName
#AutoScalingGroup=$AutoScalingGroup
#CLUSTERID=$ClusterID

Region=""
StackName=""
AutoScalingGroup=""
CLUSTERID=""

if [ -z "$Region" ]; then
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    Region=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/dynamic/instance-identity/document | grep -oP '\"region\"[[:space:]]*:[[:space:]]*\"\K[^\"]+')
fi

if [ -z "$StackName" ]; then
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    Region=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/dynamic/instance-identity/document | grep -oP '\"region\"[[:space:]]*:[[:space:]]*\"\K[^\"]+')
    Instanceid=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/instance-id)
    StackName=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$Instanceid" --region $Region --query "Tags[?Key == 'dish:deployment:stack-name'].Value" --output text)
fi

if [ -z "$AutoScalingGroup" ]; then
    TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    Region=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/dynamic/instance-identity/document | grep -oP '\"region\"[[:space:]]*:[[:space:]]*\"\K[^\"]+')
    Instanceid=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/instance-id)
    AutoScalingGroup=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$Instanceid" --region $Region --query "Tags[?Key == 'aws:cloudformation:logical-id'].Value" --output text)
fi

KUBEFILE=/var/lib/kubelet/kubeconfig
DATE=$(date)
let totalTime=0
LOGFILE=/var/log/node-join-detector.log
touch $LOGFILE
while true
do
    DATE=$(date)
    if [ -e $KUBEFILE ]; then
        APISERVER=$(grep server $KUBEFILE | sed -e 's/^[[:space:]]*//' | cut -f2 -d " ")
        if [ -z "$CLUSTERID" ]; then
            CLUSTERID=$(grep -E -A1 "\"\-i\"" $KUBEFILE | grep -E -v "\"\-i\"" | sed -e 's/^[[:space:]]*//' | cut -f2 -d "\"")
        fi
        REGION=$Region
        echo "$DATE found kubeconfig, APISERVER=$APISERVER, CLUSTERID=$CLUSTERID, REGION=$REGION" >> $LOGFILE
        
        let token_get_count=0
        while true
        do
            TOKEN=$(/usr/bin/aws-iam-authenticator token --region $REGION --token-only -i $CLUSTERID)
            if [ ! -z "$TOKEN" ]; then
                echo "$DATE found token!" >> $LOGFILE
                break
            elif [ $token_get_count -gt 3 ]; then
                echo "$DATE could not get token after 3 tries" >> $LOGFILE
                echo "$DATE node $HOSTNAME with ID $Instanceid will be terminated" >> $LOGFILE
    	        aws ec2 terminate-instances --instance-ids $Instanceid --region $Region
                exit 1
            fi
            let token_get_count=$token_get_count+1
            sleep 5
            let totalTime=$totalTime+5
        done
        if [ ! -z "$TOKEN" ]; then
            (curl -X GET $APISERVER/api/v1/nodes/$HOSTNAME --header "Authorization: Bearer $TOKEN" --insecure > /var/tmp/status) >> $LOGFILE 2>&1
            if grep -E -A5  "\"type\"\: \"Ready\"" /var/tmp/status | grep -q "True" 
            then
                echo "$DATE node $HOSTNAME has joined the cluster $CLUSTERID" >> $LOGFILE
                sleep 60
                /opt/aws/bin/cfn-signal -s true \
                         --stack  $StackName \
                         --resource $AutoScalingGroup  \
                         --region $Region
                exit 0
            fi    
        fi
    fi
    sleep 5
    let totalTime=$totalTime+5
    if [ $totalTime -gt 600 ]; then
        echo "$DATE exiting, could not find kubeconfig within the 10 minute window.." >> $LOGFILE
        echo "$DATE node $HOSTNAME with ID $Instanceid will be terminated" >> $LOGFILE
    	aws ec2 terminate-instances --instance-ids $Instanceid --region $Region
        exit 1
    fi
done