## VPP DPDK Deployment

VPP will be used to test the DPDK infrastructure that was built. An helm chart has been provided also in this folder.

Follow the steps to deploy the VPP CNF:

* Build the DPDK IP management container image, this will be used to sync the DPDK secondary IPs to the respective EC2 ENI interfaces. Instructions can be found at ***container-building/README.md***

* Install the SRIOV-Device Plugin (take note that a configmap is not been used, the config.json has been created via the cloud formation and it's been mounted as hostPath in the sriov-device-plugin daemonset manifest):

  ```
  kubectl create -f sriovdp-ds.yaml
  ```

* Replace ECR_REPO with your image repo in the following sections in the helm-chart/values.yaml file:

  ```
  dpdk:
    awsipmgmt:
      repository: ECR_REPO/dpdk-aws-ipmgt
      version: v0.1
      pullPolicy: IfNotPresent
  ```

* Deploy the VPP CNF helm-chart:

  ```
  helm -n dpdk upgrade --install core --create-namespace ./helm-chart
  ```

## Check Status Of the VPP To Confirm DPDK

Check environement variables to confirm that sriov device plugin injected the DPDK interface into the POD:

```
kubectl -n dpdk exec -ti deploy/core-vpp-dpdk printenv | grep PCI

PCIDEVICE_INTEL_COM_INTEL_SRIOV_NETDEVICE_3=0000:00:08.0
PCIDEVICE_INTEL_COM_INTEL_SRIOV_NETDEVICE_1=0000:00:06.0
PCIDEVICE_INTEL_COM_INTEL_SRIOV_NETDEVICE_2=0000:00:07.0
```

Exec into the VPP CLI:

```
kubectl -n dpdk exec -ti deploy/core-vpp-dpdk vppctl
kubectl exec [POD] [COMMAND] is DEPRECATED and will be removed in a future version. Use kubectl exec [POD] -- [COMMAND] instead.
Defaulted container "vpp" out of: vpp, dpdk-sync-aws-ip (init)
    _______    _        _   _____  ___
 __/ __/ _ \  (_)__    | | / / _ \/ _ \
 _/ _// // / / / _ \   | |/ / ___/ ___/
 /_/ /____(_)_/\___/   |___/_/  /_/

vpp#
vpp#
vpp#
```

Commands to show the DPDK state

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
```

```
vpp# show dpdk version
DPDK Version:             DPDK 22.07.0
DPDK EAL init args:       --in-memory --no-telemetry --file-prefix vpp -a 0000:00:06.0 -a 0000:00:07.0 -a 0000:00:08.0
```

Create an EC2 instance in one of the Multus subnets and initiate ping towards the DPDK interfaces that also belongs to the subnet you created the instance in and run a DPDK trace in VPP to see the traffic input:

```
vpp#trace add dpdk-input 100

vpp#show trace
------------------- Start of thread 1 vpp_wk_0 -------------------
Packet 1

00:27:42:097243: dpdk-input
  net1 rx queue 0
  buffer 0xfff6b7: current data 0, length 98, buffer-pool 0, ref-count 1, trace handle 0x1000000
                   ext-hdr-valid
  PKT MBUF: port 0, nb_segs 1, pkt_len 98
    buf_len 2176, data_len 98, ol_flags 0x80, data_off 128, phys_addr 0xfffdae40
    packet_type 0x10 l2_len 0 l3_len 0 outer_l2_len 0 outer_l3_len 0
    rss 0x0 fdir.hi 0x0 fdir.lo 0x0
    Packet Offload Flags
      PKT_RX_IP_CKSUM_GOOD (0x0080) IP cksum of RX pkt. is valid
      PKT_RX_IP_CKSUM_NONE (0x0090) no IP cksum of RX pkt.
    Packet Types
      RTE_PTYPE_L3_IPV4 (0x0010) IPv4 packet without extension headers
  IP4: 02:87:00:a7:5e:eb -> 02:16:5e:d0:36:cf
  ICMP: 192.168.6.53 -> 192.168.6.8
    tos 0x00, ttl 127, length 84, checksum 0xd3e4 dscp CS0 ecn NON_ECN
    fragment id 0x9a36, flags DONT_FRAGMENT
  ICMP echo_request checksum 0x5181 id 4
00:27:42:097248: ethernet-input
  frame: flags 0x3, hw-if-index 1, sw-if-index 1
  IP4: 02:87:00:a7:5e:eb -> 02:16:5e:d0:36:cf
00:27:42:097250: ip4-input-no-checksum
  ICMP: 192.168.6.53 -> 192.168.6.8
    tos 0x00, ttl 127, length 84, checksum 0xd3e4 dscp CS0 ecn NON_ECN
    fragment id 0x9a36, flags DONT_FRAGMENT
  ICMP echo_request checksum 0x5181 id 4
00:27:42:097251: ip4-lookup
  fib 0 dpo-idx 7 flow hash: 0x00000000
  ICMP: 192.168.6.53 -> 192.168.6.8
    tos 0x00, ttl 127, length 84, checksum 0xd3e4 dscp CS0 ecn NON_ECN
    fragment id 0x9a36, flags DONT_FRAGMENT
  ICMP echo_request checksum 0x5181 id 4
00:27:42:097252: ip4-receive
    ICMP: 192.168.6.53 -> 192.168.6.8
      tos 0x00, ttl 127, length 84, checksum 0xd3e4 dscp CS0 ecn NON_ECN
      fragment id 0x9a36, flags DONT_FRAGMENT
    ICMP echo_request checksum 0x5181 id 4
00:27:42:097253: ip4-icmp-input
  ICMP: 192.168.6.53 -> 192.168.6.8
    tos 0x00, ttl 127, length 84, checksum 0xd3e4 dscp CS0 ecn NON_ECN
    fragment id 0x9a36, flags DONT_FRAGMENT
  ICMP echo_request checksum 0x5181 id 4
00:27:42:097253: ip4-icmp-echo-request
  ICMP: 192.168.6.53 -> 192.168.6.8
    tos 0x00, ttl 127, length 84, checksum 0xd3e4 dscp CS0 ecn NON_ECN
    fragment id 0x9a36, flags DONT_FRAGMENT
  ICMP echo_request checksum 0x5181 id 4
00:27:42:097254: ip4-load-balance
  fib 0 dpo-idx 6 flow hash: 0x00000000
  ICMP: 192.168.6.8 -> 192.168.6.53
    tos 0x00, ttl 64, length 84, checksum 0x4278 dscp CS0 ecn NON_ECN
    fragment id 0x6aa3, flags DONT_FRAGMENT
  ICMP echo_reply checksum 0x5981 id 4
00:27:42:097255: ip4-rewrite
  tx_sw_if_index 1 dpo-idx 6 : ipv4 via 192.168.6.53 net1: mtu:9000 next:3 flags:[] 028700a75eeb02165ed036cf0800 flow hash: 0x00000000
  00000000: 028700a75eeb02165ed036cf0800450000546aa3400040014278c0a80608c0a8
  00000020: 0635000059810004000140249a6400000000ff1d0e00000000001011
00:27:42:097255: net1-output
  net1
  IP4: 02:16:5e:d0:36:cf -> 02:87:00:a7:5e:eb
  ICMP: 192.168.6.8 -> 192.168.6.53
    tos 0x00, ttl 64, length 84, checksum 0x4278 dscp CS0 ecn NON_ECN
    fragment id 0x6aa3, flags DONT_FRAGMENT
  ICMP echo_reply checksum 0x5981 id 4
00:27:42:097256: net1-tx
  net1 tx queue 1
  buffer 0xfff6b7: current data 0, length 98, buffer-pool 0, ref-count 1, trace handle 0x1000000
                   ext-hdr-valid
                   local l2-hdr-offset 0 l3-hdr-offset 14
  PKT MBUF: port 0, nb_segs 1, pkt_len 98
    buf_len 2176, data_len 98, ol_flags 0x80, data_off 128, phys_addr 0xfffdae40
    packet_type 0x10 l2_len 0 l3_len 0 outer_l2_len 0 outer_l3_len 0
    rss 0x0 fdir.hi 0x0 fdir.lo 0x0
    Packet Offload Flags
      PKT_RX_IP_CKSUM_GOOD (0x0080) IP cksum of RX pkt. is valid
      PKT_RX_IP_CKSUM_NONE (0x0090) no IP cksum of RX pkt.
    Packet Types
      RTE_PTYPE_L3_IPV4 (0x0010) IPv4 packet without extension headers
  IP4: 02:16:5e:d0:36:cf -> 02:87:00:a7:5e:eb
  ICMP: 192.168.6.8 -> 192.168.6.53
    tos 0x00, ttl 64, length 84, checksum 0x4278 dscp CS0 ecn NON_ECN
    fragment id 0x6aa3, flags DONT_FRAGMENT
  ICMP echo_reply checksum 0x5981 id 4
```

To stop the trace run the following: `clear trace`