# bootcamp-gcp-workshop

gsutil mb -p alm-bootcamp-oct-2021 -c STANDARD -l US-EAST1 gs://jony-translated-results

gcloud pubsub topics create jony-image-to-text-results

gcloud functions deploy jony-ocr-extract --runtime python39 --trigger-bucket jony-uploaded-images 

gcloud functions deploy jony-ocr-extract \
--runtime python39 \
--trigger-resource jony-uploaded-images  \
--trigger-event google.storage.object.finalize \
--entry-point process_image

gcloud functions deploy jony-ocr-translate \
--trigger-topic jony-image-to-text-translation \
--runtime python39 \
--entry-point translate_text

gcloud functions deploy jony-ocr-save \
--trigger-topic jony-image-to-text-results \
--runtime python39 \
--entry-point save_result

gcloud projects get-iam-policy alm-bootcamp-oct-2021  \
--flatten="bindings[].members" \
--format='table(bindings.role)' \
--filter="bindings.members:jony-demo"

gcloud projects add-iam-policy-binding alm-bootcamp-oct-2021 \
--member serviceAccount:jony-demo@alm-bootcamp-oct-2021.iam.gserviceaccount.com \
--role roles/editor