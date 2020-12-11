#!/bin/bash
gcp_zone=$(curl -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/zone -s | cut -d/ -f4)
VMTAG=$1
STEP=$2

cd /home/pdiachil/ml
git checkout pd_atria
git pull

sudo mount -o norecovery,discard,defaults /dev/sdb /mnt/disks/annotated-cardiac-tensors-45k/
sudo mount -o norecovery,discard,defaults /dev/sdc /mnt/disks/cardiac-raw/

cnt1=$((VMTAG*STEP))
cnt2=$((VMTAG*STEP+STEP))

/home/pdiachil/ml/scripts/tf.sh -c /home/pdiachil/ml/notebooks/mri/update_sax_test_segmentations.py $cnt1 $cnt2

/snap/bin/gsutil cp /home/pdiachil/*.hd5 gs://ml4cvd/pdiachil/segmented-sax-v20201202-2ch-v20200809-3ch-v20200603-4ch-v20201122/

yes | /snap/bin/gcloud compute instances delete $(hostname) --zone ${gcp_zone}
