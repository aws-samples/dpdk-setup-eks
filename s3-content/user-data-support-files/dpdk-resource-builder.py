import json
import sys,os
import subprocess,copy,time

def getpciAddress(intf):
    pci=""
    cmd="sudo /opt/dpdk/dpdk-devbind.py -s | grep 'if=eth"+intf+"' | awk -F ' ' '{print $1}' "
    pci=shell_run_cmd(cmd)
    print("Returned pciAddresses: " + pci + " for interface: eth"+intf)
    return pci.strip()

def shell_run_cmd(cmd,retCode=0):
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,encoding="utf-8")
    stdout, stderr = p.communicate()
    retCode = p.returncode
    return stdout

data = {}
data['resourceList'] = []
start=int(sys.argv[1])
end=int(sys.argv[2])

index=start
ctr=1
while index <= end:
    construct={}
    selectors={}
    construct["resourceName"]="intel_sriov_netdevice_"+str(ctr)
    selectors["vendors"]=["1d0f"]
    selectors["devices"]=["ec20"]
    selectors["drivers"]=["ena", "igb_uio", "vfio-pci"]
    pci =getpciAddress(str(index))
    if not pci:
        print("WARN pciaddress is empty, not adding this resource")
    else:
        selectors["pciAddresses"]=[pci]
        construct["selectors"]=selectors
        data['resourceList'].append(construct)
    index=index+1
    ctr=ctr+1
json_data = json.dumps(data,indent=4)
print(json_data)
with open('/tmp/data.txt', 'w') as outfile:
    json.dump(data, outfile,indent=4)