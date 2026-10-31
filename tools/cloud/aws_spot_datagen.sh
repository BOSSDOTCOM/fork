#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Self-play data generation on one AWS EC2 spot instance (owner,
# 2026-10-30). Run on the owner's machine with the owner's AWS CLI login;
# the repository holds no credentials, account ids or bucket names (they
# live in local, untracked settings).
#
#   tools/cloud/aws_spot_datagen.sh --bucket s3://BUCKET --instance-profile NAME [--commit REF]
#       [--generation g2] [--types T1,T2,...] [--arch auto] [--max-price 0.25] [--region us-east-2]
#       [--max-cost-per-m 0.03] [--rates tools/cloud/datagen-rates.tsv]
#       [--max-hours 12] [--chunk-positions 1000000] [--nodes 20000]
#       [--adjudicate-cp CP --adjudicate-plies N] [--bucket-region us-east-2] [--dry-run]
#
# One spot instance is requested through an instant EC2 Fleet with the
# capacity-optimized-prioritized strategy over the region's spot pools (an
# instance type in an availability zone's default subnet). Data generation
# is node-limited, so the machine type does not change the data (owner,
# 2026-10-30; the one-type rule applies to SPRTs only). Default types (all
# 8 vCPU): c8a, c7a, m7a, c7i, m7i, then c6a, c6i (.2xlarge).
# The launch rule (owner, 2026-10-30; tools/cloud/spot_pools.py): each pool's
# expected cost per million positions is its current spot price over the
# type's measured positions/s (--rates, for the commit's network, --nodes
# and the adjudication); pools above --max-cost-per-m dollars, above
# --max-price dollars an hour, or of a type with no measured rate are left
# out, the rest are the fleet's priorities, cheapest first (ties in --types
# order), each capped at the price where it reaches the cost limit. Exits 4
# when no pool has spot capacity, so a caller can retry later; 7 when no
# pool meets the rule (nothing is created); 5 or 6 when
# tools/cloud/cost_guard.sh refuses the launch (the daily cap, the credit
# floor), checked at the launch's worst case (--max-hours at --max-price)
# before anything is created, and recorded in its ledger once launched.
#
# The instance (Ubuntu 22.04 LTS, gcc 11.4):
#  1. arms a shutdown after --max-hours whatever happens (the cost cap);
#  2. picks its build target from its own CPU flags (--arch auto:
#     x86-64-v4 when it has AVX-512 F, BW, CD, DQ and VL, else x86-64-v3)
#     or uses --arch as given; clones the public repository at --commit
#     (default HEAD; it must be pushed and include 3978e91, so fork_datagen
#     names its labelling network in every manifest), builds fork and
#     fork_datagen for that target with the commit's default network, and
#     checks that `fork version` reports the target and the network and that
#     bench matches the network's reference (.github/ci/bench-parity.sh);
#  3. fetches the Syzygy 3-4-5 tables (tools/cloud/fetch_tables.sh, every
#     file checked) and regenerates the Lichess 2016-09 openings with
#     tools/datagen/datagen_openings.py (python-chess 1.11.2, zstandard
#     0.25.0, the repository's versions), which tools/cloud/cloud_datagen.sh
#     checks byte for byte against data/manifests/openings-lichess-2016-09.json
#     (the instance role can only write to S3, so nothing is read from it);
#  4. runs tools/cloud/cloud_datagen.sh on every vCPU, watched by
#     tools/cloud/spot_watch.sh, stopping 15 minutes before the shutdown;
#     each chunk is verified, sealed (with the instance type; the build
#     target is the manifest's generator arch) and uploaded to
#     s3://BUCKET/datagen/RUN/;
#  5. uploads its log and shuts down (shutting down terminates it).
# Before launching (and in a dry run) every type is checked against the
# applied spot quota (tools/cloud/spot_quota.sh) and the request is refused
# if any would exceed it. The instance, its volume and the fleet are tagged
# fork-run and fork-expires (launch time + --max-hours, UTC) for
# tools/cloud/aws_cleanup.sh; the run's launch template exists only during
# the request and is deleted afterwards.
# Regions (owner, 2026-10-30): us-east-2, us-east-1 and us-west-2, one
# instance per region within each region's own spot quota; every instance
# uploads to the bucket in --bucket-region. The run name carries the region.
# Seeds: chunk k of a run uses 10^12 + (4 x launch time in Unix seconds +
# region slot) x 1000 + k, the slot 0 for us-east-2, 1 for us-east-1, 2 for
# us-west-2: runs in different regions never share a seed even when launched
# in the same second, cloud_datagen.sh keeps k below 1000, and no local run
# comes near (local seeds are dates, about 2 x 10^7; the first cloud run,
# g2-aws-20261030T212852Z, used 10^12 + launch x 1000 + k, about 2.8 x 10^12,
# below every seed of this rule). Bring the data home with
# tools/cloud/pull_datagen.sh. FORK_AWS names the AWS CLI command (the
# tests use a stub).
set -euo pipefail
aws=${FORK_AWS:-aws}
repo_url=https://github.com/BOSSDOTCOM/fork.git
openings_url=https://database.lichess.org/standard/lichess_db_standard_rated_2016-09.pgn.zst
types=c8a.2xlarge,c7a.2xlarge,m7a.2xlarge,c7i.2xlarge,m7i.2xlarge,c6a.2xlarge,c6i.2xlarge
arch=auto max_price=0.25 region=${AWS_REGION:-us-east-2} max_hours=12 chunk=1000000 nodes=20000
adj_cp=0 adj_plies=0 bucket_region=us-east-2 max_cost=0.03 rates=""
generation=g2 bucket="" profile="" commit=HEAD dry=0
while [ $# -gt 0 ]; do
  case $1 in
    --bucket) bucket=$2 ;; --instance-profile) profile=$2 ;; --commit) commit=$2 ;; --generation) generation=$2 ;;
    --types | --type) types=$2 ;; --arch) arch=$2 ;; --max-price) max_price=$2 ;; --region) region=$2 ;;
    --max-hours) max_hours=$2 ;; --chunk-positions) chunk=$2 ;; --nodes) nodes=$2 ;;
    --adjudicate-cp) adj_cp=$2 ;; --adjudicate-plies) adj_plies=$2 ;; --bucket-region) bucket_region=$2 ;;
    --max-cost-per-m) max_cost=$2 ;; --rates) rates=$2 ;;
    --dry-run) dry=1; shift; continue ;;
    *) echo "aws_spot_datagen.sh: unknown option $1" >&2; exit 2 ;;
  esac
  shift 2
done
for v in bucket profile; do
  [ -n "${!v}" ] || { echo "aws_spot_datagen.sh: --${v/profile/instance-profile} is required" >&2; exit 2; }
done
case "$max_hours$chunk$nodes$adj_cp$adj_plies" in *[!0-9]*) echo "numbers expected" >&2; exit 2 ;; esac
[[ $max_price =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "aws_spot_datagen.sh: --max-price in dollars, like 0.25" >&2; exit 2; }
[[ $max_cost =~ ^[0-9]+(\.[0-9]+)?$ ]] || { echo "aws_spot_datagen.sh: --max-cost-per-m in dollars, like 0.03" >&2; exit 2; }
IFS=, read -r -a type_list <<<"$types"
[ ${#type_list[@]} -gt 0 ] || { echo "aws_spot_datagen.sh: --types is empty" >&2; exit 2; }
for t in "${type_list[@]}"; do
  case $t in c6a.* | c6i.* | c7a.* | c7i.* | c8a.* | m7a.* | m7i.*) ;;
    *) echo "aws_spot_datagen.sh: $t: c6a, c6i, c7a, c7i, c8a, m7a or m7i types only" >&2; exit 2 ;;
  esac
done
case $arch in auto | x86-64-v3 | x86-64-v4) ;; *) echo "aws_spot_datagen.sh: --arch auto, x86-64-v3 or x86-64-v4" >&2; exit 2 ;; esac
case $generation in g[0-9]*) ;; *) echo "aws_spot_datagen.sh: --generation like g2" >&2; exit 2 ;; esac
case $region in
  us-east-2) slot=0 ;; us-east-1) slot=1 ;; us-west-2) slot=2 ;;
  *) echo "aws_spot_datagen.sh: --region us-east-2, us-east-1 or us-west-2" >&2; exit 2 ;;
esac
[[ $bucket_region =~ ^[a-z]{2}-[a-z]+-[0-9]$ ]] || { echo "aws_spot_datagen.sh: --bucket-region like us-east-2" >&2; exit 2; }
here=$(cd "$(dirname "$0")/../.." && pwd)
rates=${rates:-$here/tools/cloud/datagen-rates.tsv}
[ -f "$rates" ] || { echo "aws_spot_datagen.sh: no rates file $rates" >&2; exit 2; }
adjudicate=$adj_cp/$adj_plies
[ "$adj_cp" = 0 ] && adjudicate=off
commit=$(git -C "$here" rev-parse --verify "$commit^{commit}")
git -C "$here" merge-base --is-ancestor 3978e91 "$commit" ||
  { echo "aws_spot_datagen.sh: $commit predates 3978e91 (manifests would not name the net)" >&2; exit 2; }
net=$(git -C "$here" show "$commit:CMakeLists.txt" | sed -n 's|^set(FORK_NET "${CMAKE_SOURCE_DIR}/nets/\([a-z0-9]*\)\.fnet".*|\1|p')
[ -n "$net" ] || { echo "aws_spot_datagen.sh: no default network found at $commit" >&2; exit 2; }
launch=$(date -u +%s)
seed_base=$((1000000000000 + (4 * launch + slot) * 1000))
run=$generation-aws-$region-$(date -u -d "@$launch" +%Y%m%dT%H%M%SZ)
expires=$(date -u -d "@$((launch + max_hours * 3600))" +%Y-%m-%dT%H:%M:%SZ)
source_sha=$(git -C "$here" show "$commit:data/manifests/openings-lichess-2016-09.json" |
  sed -n 's/.*"source_sha256": "\([0-9a-f]*\)".*/\1/p')
[ ${#source_sha} = 64 ] || { echo "aws_spot_datagen.sh: no openings source SHA-256 at $commit" >&2; exit 2; }

user_data() {
  cat <<EOF
#!/bin/bash
# Fork cloud data generation $run, generated by tools/cloud/aws_spot_datagen.sh.
exec >/var/log/fork-datagen.log 2>&1
set -uo pipefail
# Instance $region, bucket $bucket_region: every S3 call goes to the bucket's region.
export AWS_DEFAULT_REGION=$bucket_region
shutdown -h +$((max_hours * 60))
stop_at=\$(( \$(date +%s) + $((max_hours * 3600 - 900)) ))
fail() { echo "FAILED: \$1"; aws s3 cp --only-show-errors /var/log/fork-datagen.log ${bucket%/}/datagen/$run/boot.log; shutdown -h now; exit 1; }
export DEBIAN_FRONTEND=noninteractive HOME=/root
tok=\$(curl -sS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')
itype=\$(curl -sS -H "X-aws-ec2-metadata-token: \$tok" http://169.254.169.254/latest/meta-data/instance-type)
flags=" \$(grep -m1 '^flags' /proc/cpuinfo | cut -d: -f2) "
has() { for f in "\$@"; do case \$flags in *" \$f "*) ;; *) return 1 ;; esac; done; }
has avx2 bmi2 fma || fail "\$itype: no AVX2, BMI2 and FMA"
arch=$arch
if [ "\$arch" = auto ]; then
  arch=x86-64-v3
  has avx512f avx512bw avx512cd avx512dq avx512vl && arch=x86-64-v4
fi
[ "\$arch" = x86-64-v3 ] || has avx512f avx512bw avx512cd avx512dq avx512vl || fail "\$itype: \$arch needs AVX-512"
echo "instance \$itype (\$(grep -m1 '^model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ *//')), build \$arch"
apt-get update -q && apt-get install -y -q build-essential cmake ninja-build git python3 python3-venv curl awscli || fail apt
git clone -q $repo_url /opt/fork && cd /opt/fork && git checkout -q $commit || fail clone
cmake -S . -B build/dg -G Ninja -DCMAKE_CXX_COMPILER=g++ -DCMAKE_BUILD_TYPE=Release -DFORK_ARCH=\$arch -DFORK_BUILD_TESTS=OFF || fail configure
cmake --build build/dg --target fork fork_datagen || fail build
build/dg/fork version | grep -qx "arch \$arch" || fail "the build's target is not \$arch"
build/dg/fork version | grep -qx "net $net" || fail "the build's network is not $net"
bash .github/ci/bench-parity.sh build/dg/fork || fail bench
bash tools/cloud/fetch_tables.sh /opt/syzygy || fail tables
python3 -m venv /opt/venv && /opt/venv/bin/pip install -q chess==1.11.2 zstandard==0.25.0 || fail python
mkdir -p /opt/openings
curl -sSfL $openings_url | /opt/venv/bin/python -I tools/datagen/datagen_openings.py - /opt/openings/lichess-2016-09.epd \\
  --sha256 $source_sha --source-name lichess_db_standard_rated_2016-09.pgn.zst --seed 20261028 || fail openings
PYTHON=/opt/venv/bin/python bash tools/cloud/cloud_datagen.sh --run $run --seed-base $seed_base \\
  --datagen build/dg/fork_datagen --openings /opt/openings/lichess-2016-09.epd \\
  --openings-manifest data/manifests/openings-lichess-2016-09.json --tables /opt/syzygy \\
  --upload-to ${bucket%/}/datagen/$run --chunk-positions $chunk --nodes $nodes --stop-at \$stop_at \\
  --instance-type "\$itype" --adjudicate-cp $adj_cp --adjudicate-plies $adj_plies &
job=\$!
bash tools/cloud/spot_watch.sh \$job &
wait \$job
aws s3 cp --only-show-errors /var/log/fork-datagen.log ${bucket%/}/datagen/$run/boot.log
shutdown -h now
EOF
}

tags="{\"Key\":\"fork-run\",\"Value\":\"$run\"},{\"Key\":\"fork-expires\",\"Value\":\"$expires\"}"
# The pools that meet the launch rule, as the fleet's overrides (JSON) in
# $tmp/overrides.json, from the region's default subnets and current spot
# prices (read-only calls); returns 7 when none does.
choose_pools() {
  local rc=0
  "$aws" ec2 describe-subnets --region "$region" --filters Name=default-for-az,Values=true \
    --query 'Subnets[].[SubnetId,AvailabilityZone]' --output json >"$tmp/subnets.json"
  "$aws" ec2 describe-spot-price-history --region "$region" --instance-types "${type_list[@]}" \
    --product-descriptions Linux/UNIX --start-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --query 'SpotPriceHistory[].[AvailabilityZone,InstanceType,SpotPrice,Timestamp]' --output json >"$tmp/prices.json"
  echo "spot pools in $region by expected cost (at most \$$max_cost per million positions, \$$max_price/h):"
  "${PYTHON:-python3}" "$here/tools/cloud/spot_pools.py" --rates "$rates" --net "$net" --nodes "$nodes" \
    --adjudicate "$adjudicate" --types "$types" --max-price "$max_price" --max-cost-per-m "$max_cost" \
    --prices "$tmp/prices.json" --subnets "$tmp/subnets.json" >"$tmp/overrides.json" 2>"$tmp/pools.txt" || rc=$?
  tr -d '\r' <"$tmp/pools.txt"
  case $rc in 0) ;; 3) return 7 ;; *) echo "aws_spot_datagen.sh: spot_pools.py failed ($rc)" >&2; exit 1 ;; esac
}
# The fleet request over the chosen pools (their priorities and price caps).
fleet_config() {  # overrides JSON
  cat <<EOF
{"Type":"instant",
 "LaunchTemplateConfigs":[{"LaunchTemplateSpecification":{"LaunchTemplateName":"fork-$run","Version":"\$Latest"},
   "Overrides":$1}],
 "TargetCapacitySpecification":{"TotalTargetCapacity":1,"SpotTargetCapacity":1,"DefaultTargetCapacityType":"spot"},
 "SpotOptions":{"AllocationStrategy":"capacity-optimized-prioritized","InstanceInterruptionBehavior":"terminate",
   "MaxTotalPrice":"$max_price"},
 "TagSpecifications":[{"ResourceType":"fleet","Tags":[$tags]}]}
EOF
}

echo "run $run: 1 spot instance of $types (the rule: at most \$$max_cost per million positions, \$$max_price/h), build $arch,"
echo "  labelled by $net (commit ${commit:0:7}), chunks of $chunk positions at $nodes nodes, score adjudication $adj_cp cp x $adj_plies plies (0: off),"
echo "  seeds from $seed_base, max $max_hours h (expires $expires), data to ${bucket%/}/datagen/$run/"
quota_ok=1
check_quota() {
  local t
  for t in "${type_list[@]}"; do
    bash "$here/tools/cloud/spot_quota.sh" --region "$region" --type "$t" --count 1 || quota_ok=0
  done
}
# The spending guards (tools/cloud/cost_guard.sh): this launch at its worst
# case, every hour it may run at the price cap.
worst=$(awk -v h="$max_hours" -v p="$max_price" 'BEGIN { printf "%.2f", h * p }')
tmp=$(mktemp -d)
template_made=0
cleanup() {
  [ $template_made = 1 ] && "$aws" ec2 delete-launch-template --region "$region" --launch-template-name "fork-$run" \
    >/dev/null
  rm -rf "$tmp"
}
trap cleanup EXIT
echo '[]' >"$tmp/overrides.json"
if [ "$dry" = 1 ]; then
  if command -v "$aws" >/dev/null; then
    check_quota
    [ $quota_ok = 1 ] || echo "(dry run: this launch would be refused)"
    bash "$here/tools/cloud/cost_guard.sh" check "$worst" || echo "(dry run: the cost guard would refuse it)"
    choose_pools || echo "(dry run: no pool meets the launch rule; nothing would launch)"
  fi
  echo "--- tags: Name=fork-$run, fork-run=$run, fork-expires=$expires"
  echo "--- fleet request (pools as ranked now; dry run: nothing is launched)"
  fleet_config "$(cat "$tmp/overrides.json")"
  echo "--- user data"
  user_data
  exit 0
fi
command -v "$aws" >/dev/null || { echo "aws_spot_datagen.sh: the AWS CLI is not installed" >&2; exit 1; }
git -C "$here" branch -r --contains "$commit" | grep -q . ||
  { echo "aws_spot_datagen.sh: $commit is not pushed (the instance clones the public repository)" >&2; exit 2; }
check_quota
[ $quota_ok = 1 ] || exit 3
bash "$here/tools/cloud/cost_guard.sh" check "$worst" || exit $?
rc=0
choose_pools || rc=$?
[ $rc = 0 ] || { echo "no instance launched: no spot pool meets the launch rule"; exit $rc; }
ami=$("$aws" ssm get-parameter --region "$region" --query Parameter.Value --output text \
  --name /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id)
user_data >"$tmp/ud"
cat >"$tmp/template.json" <<EOF
{"ImageId":"$ami","IamInstanceProfile":{"Name":"$profile"},"UserData":"$(base64 -w0 "$tmp/ud")",
 "InstanceInitiatedShutdownBehavior":"terminate",
 "TagSpecifications":[{"ResourceType":"instance","Tags":[{"Key":"Name","Value":"fork-$run"},$tags]},
   {"ResourceType":"volume","Tags":[$tags]}]}
EOF
"$aws" ec2 create-launch-template --region "$region" --launch-template-name "fork-$run" \
  --launch-template-data "file://$tmp/template.json" >/dev/null
template_made=1
fleet_config "$(cat "$tmp/overrides.json")" >"$tmp/fleet.json"
"$aws" ec2 create-fleet --region "$region" --cli-input-json "file://$tmp/fleet.json" \
  --query '{i: Instances[].[InstanceIds[0], InstanceType], e: Errors[].[ErrorCode, LaunchTemplateAndOverrides.Overrides.InstanceType]}' \
  --output json >"$tmp/out.json"
read -r id itype < <("${PYTHON:-python3}" -c 'import json,sys; i=json.load(open(sys.argv[1]))["i"] or [["", ""]]; print(*i[0])' \
  "$tmp/out.json" | tr -d '\r')
if [ -z "$id" ]; then
  "${PYTHON:-python3}" -c 'import collections,json,sys
e=json.load(open(sys.argv[1]))["e"] or []
print("no instance launched:", ", ".join(f"{c} ({n})" for c, n in collections.Counter(c for c, _ in e).items()) or "no reason given")' \
    "$tmp/out.json"
  exit 4
fi
bash "$here/tools/cloud/cost_guard.sh" record "$run" "$worst"
echo "launched $id ($itype); follow with: aws s3 ls ${bucket%/}/datagen/$run/ --recursive"
