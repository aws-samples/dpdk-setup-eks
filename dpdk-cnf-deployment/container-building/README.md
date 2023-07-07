# How To Build The Container Images

This readme covers how to build the DPDK AWS IP Management container image that is required to build the VPP CNF deployment

### Create ECR Repo

```plaintext
export AWS_REGION=us-west-2
export AWS_ACCOUNT_NUMBER=$()
aws --region ${AWS_REGION} ecr create-repository --repository-name dpdk-aws-ipmgt
```

### Build The DPDK AWS IP MGT Container Image

```
sudo docker build -t ${AWS_ACCOUNT_NUMBER}.dkr.ecr.${AWS_REGION}.amazonaws.com/dpdk-aws-ipmgt:v0.1 -f dpdk-aws-ipmgt-dockerfile .
```

### Login To ECR And Push Container Images

```
aws ecr get-login-password --region ${AWS_REGION} | sudo docker login --username AWS --password-stdin ${AWS_ACCOUNT_NUMBER}.dkr.ecr.${AWS_REGION}.amazonaws.com

sudo docker push ${AWS_ACCOUNT_NUMBER}.dkr.ecr.${AWS_REGION}.amazonaws.com/dpdk-aws-ipmgt:v0.1
```

Replace the container image repo details in the ***values.yaml*** with the the one that was built above.