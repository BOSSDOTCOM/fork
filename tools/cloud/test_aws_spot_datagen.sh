#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Tests of tools/cloud/aws_spot_datagen.sh with a stub AWS CLI (FORK_AWS):
# the fleet request it builds (every type in every subnet, in priority
# order, each under the price cap), the instance's build-target choice in
# its user data, the quota refusal, and the launch template's cleanup on
# success and on no capacity. No AWS account is needed.
#
#   bash tools/cloud/test_aws_spot_datagen.sh
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
failures=0
check() {  # description, command...
  local what=$1
  shift
  if "$@"; then echo "PASS  $what"; else echo "FAIL  $what"; failures=$((failures + 1)); fi
}
cat >"$tmp/aws" <<'EOF'
#!/usr/bin/env bash
# Stub: STUB_QUOTA, STUB_FLEET (ok | none); records calls in $STUB_DIR.
echo "$1 $2" >>"$STUB_DIR/calls"
case "$1 $2" in
  "service-quotas get-service-quota") echo "$STUB_QUOTA" ;;
  "ec2 describe-instance-types") echo 8 ;;
  "ec2 describe-instances") echo "" ;;
  "ec2 describe-subnets") echo "subnet-1 subnet-2" ;;
  "ssm get-parameter") echo ami-123 ;;
  "ec2 create-launch-template")
    for a in "$@"; do case $a in file://*) cp "${a#file://}" "$STUB_DIR/template.json" ;; esac; done ;;
  "ec2 delete-launch-template") echo deleted >"$STUB_DIR/deleted" ;;
  "ec2 create-fleet")
    for a in "$@"; do case $a in file://*) cp "${a#file://}" "$STUB_DIR/fleet.json" ;; esac; done
    if [ "$STUB_FLEET" = ok ]; then
      echo '{"i": [["i-123", "c8a.2xlarge"]], "e": [["InsufficientInstanceCapacity", "c7a.2xlarge"]]}'
    else
      echo '{"i": [], "e": [["InsufficientInstanceCapacity", "c7a.2xlarge"], ["InsufficientInstanceCapacity", "c6i.2xlarge"]]}'
    fi ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$tmp/aws"
export FORK_AWS=$tmp/aws STUB_QUOTA=8.0 FORK_LAUNCH_LEDGER=$tmp/ledger.tsv
unset FORK_CREDITS_START FORK_DAILY_CAP
launcher=(bash "$here/aws_spot_datagen.sh" --bucket s3://b --instance-profile p --region us-east-1)
# A pushed commit with a default network (B0r2) whose manifests name it.
commit=3978e91

# 1. Usage errors.
"${launcher[@]}" --types c7a.2xlarge,t3.large --dry-run >"$tmp/o" 2>&1
check "a type outside the list is refused" [ $? -eq 2 ]
"${launcher[@]}" --max-price 1e3 --dry-run >"$tmp/o" 2>&1
check "a malformed price is refused" [ $? -eq 2 ]
"${launcher[@]}" --region eu-west-1 --dry-run >"$tmp/o" 2>&1
check "a region outside the three is refused" [ $? -eq 2 ]

# 1b. Regions: each run's seeds carry its region's slot (us-east-2 0,
# us-east-1 1, us-west-2 2), its name the region, and its uploads go to the
# bucket's region.
for rs in us-east-2:0 us-east-1:1 us-west-2:2; do
  r=${rs%:*} s=${rs#*:}
  bash "$here/aws_spot_datagen.sh" --bucket s3://b --instance-profile p --region "$r" --commit HEAD --dry-run \
    >"$tmp/d-$r" 2>&1
  base=$(sed -n 's/.*seeds from \([0-9]*\),.*/\1/p' "$tmp/d-$r")
  slot_ok() { [ -n "$1" ] && [ $((($1 - 1000000000000) / 1000 % 4)) -eq "$2" ] && [ $(($1 % 1000)) -eq 0 ]; }
  check "$r: the seed base carries slot $s" slot_ok "$base" "$s"
  check "$r: the run is named after its region" grep -q "^run g2-aws-$r-" "$tmp/d-$r"
  check "$r: uploads go to the bucket's region" grep -qx "export AWS_DEFAULT_REGION=us-east-2" "$tmp/d-$r"
done

if ! git -C "$here" branch -r --contains "$commit" 2>/dev/null | grep -q .; then
  echo "SKIP  launch cases: $commit is not on a remote branch in this clone"
else
  # 2. A launch with capacity.
  export STUB_DIR=$tmp/s1 STUB_FLEET=ok
  mkdir -p "$STUB_DIR"
  "${launcher[@]}" --commit $commit >"$tmp/o1" 2>&1
  check "a launch with capacity succeeds" [ $? -eq 0 ]
  check "it reports the instance and its type" grep -q "launched i-123 (c8a.2xlarge)" "$tmp/o1"
  check "the launch template is deleted afterwards" [ -f "$STUB_DIR/deleted" ]
  check "the fleet asks for every type in every subnet, in order, under the cap" "${PYTHON:-python3}" -c '
import json, sys
f = json.load(open(sys.argv[1]))
o = f["LaunchTemplateConfigs"][0]["Overrides"]
types = "c7a c8a m7a c7i m7i c6a c6i".split()
want = [(t + ".2xlarge", s, i + 1) for i, t in enumerate(types) for s in ("subnet-1", "subnet-2")]
ok = [(x["InstanceType"], x["SubnetId"], x["Priority"]) for x in o] == want
ok &= all(x["MaxPrice"] == "0.25" for x in o)
ok &= f["Type"] == "instant" and f["TargetCapacitySpecification"]["TotalTargetCapacity"] == 1
ok &= f["SpotOptions"]["AllocationStrategy"] == "capacity-optimized-prioritized"
ok &= f["SpotOptions"]["MaxTotalPrice"] == "0.25"
sys.exit(not ok)' "$STUB_DIR/fleet.json"
  "${PYTHON:-python3}" -c 'import base64, json, sys
print(base64.b64decode(json.load(open(sys.argv[1]))["UserData"]).decode())' "$STUB_DIR/template.json" >"$tmp/ud"
  check "the instance picks x86-64-v4 only with all five AVX-512 flags" \
    grep -q 'has avx512f avx512bw avx512cd avx512dq avx512vl && arch=x86-64-v4' "$tmp/ud"
  check "the build is checked to report its target" grep -qF 'grep -qx "arch $arch"' "$tmp/ud"
  check "the chunks record the instance type" grep -qF -- '--instance-type "$itype"' "$tmp/ud"
  check "the instance and its volume are tagged" "${PYTHON:-python3}" -c '
import json, sys
t = json.load(open(sys.argv[1]))["TagSpecifications"]
sys.exit(not all({"fork-run", "fork-expires"} <= {x["Key"] for x in s["Tags"]} for s in t))' "$STUB_DIR/template.json"

  # 3. No capacity anywhere: exit 4, the reason, the template deleted.
  export STUB_DIR=$tmp/s2 STUB_FLEET=none
  mkdir -p "$STUB_DIR"
  "${launcher[@]}" --commit $commit >"$tmp/o2" 2>&1
  check "no capacity exits 4" [ $? -eq 4 ]
  check "it says why" grep -q "no instance launched: InsufficientInstanceCapacity (2)" "$tmp/o2"
  check "the launch template is deleted after a failure too" [ -f "$STUB_DIR/deleted" ]

  # 4. Over the quota: refused before any template or fleet exists.
  export STUB_DIR=$tmp/s3 STUB_QUOTA=4.0
  mkdir -p "$STUB_DIR"
  "${launcher[@]}" --commit $commit >"$tmp/o3" 2>&1
  check "a launch over the quota is refused" [ $? -eq 3 ]
  check "nothing is created" bash -c "! grep -q 'create-' '$STUB_DIR/calls'"

  # 5. The cost guard: the successful launch above was recorded at its worst
  # case (12 h at $0.25), and launches beyond the daily cap are refused
  # before anything is created.
  check "the launch was recorded in the ledger at \$3.00" grep -q $'\t3.00$' "$FORK_LAUNCH_LEDGER"
  export STUB_DIR=$tmp/s4 STUB_QUOTA=8.0 FORK_DAILY_CAP=5
  mkdir -p "$STUB_DIR"
  "${launcher[@]}" --commit $commit >"$tmp/o4" 2>&1
  check "a launch over the daily cap is refused (exit 5)" [ $? -eq 5 ]
  check "nothing is created over the cap" bash -c "! grep -q 'create-' '$STUB_DIR/calls'"
  unset FORK_DAILY_CAP
fi

echo "$failures failure(s)"
[ $failures -eq 0 ]
