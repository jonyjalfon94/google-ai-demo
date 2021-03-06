# Own The Cloud - Demystifying AI on GCP

In this repo you will find all the resources used during the "Demystifying AI on GCP" session which was part of the Own The Cloud event in 2022.

During the talk we saw how we can build "smart applications" that interact with various Google Cloud AI services using the pre-trained models that are available through their APIs.

The demo "Meme Generator" application stores images and allows the user to generate, translate and read the text from memes by using the following APIs through their client libraries:
- [Google Cloud Storage](https://cloud.google.com/storage/)
- [Google Cloud Datastore](https://cloud.google.com/datastore/)
- [Google Cloud Vision API](https://cloud.google.com/vision/)
- [Google Cloud Translate API](https://cloud.google.com/translate/)
- [Google Cloud Talk-to-Speech API](https://cloud.google.com/text-to-speech)

The demo application is hosted using [Google App Engine](https://cloud.google.com/appengine).

## Setup

Create a new project with the [Google Cloud Platform console](https://console.cloud.google.com/).
Make a note of your project ID, which may be different than your project name.

Make sure to [Enable Billing](https://pantheon.corp.google.com/billing?debugUI=DEVELOPERS)
for your project.

Download the [Google Cloud SDK](https://cloud.google.com/sdk/docs/) to your
local machine. Alternatively, you could use the [Cloud Shell](https://cloud.google.com/shell/docs/quickstart), which comes with the Google Cloud SDK pre-installed.

Initialize the Google Cloud SDK (skip if using Cloud Shell):

    gcloud init

Create your App Engine application:

    gcloud app create

Set an environment variable for your project ID, replacing `[YOUR_PROJECT_ID]`
with your project ID:

    export PROJECT_ID=[YOUR_PROJECT_ID]

## Getting the sample code

Run the following command to clone the Github repository:

    git clone https://github.com/jonyjalfon94/google-ai-demo.git

Change directory to the sample code location:

    cd google-ai-demo/app-engine

## Authentication

Enable the APIs:

    gcloud services enable storage-component.googleapis.com
    gcloud services enable datastore.googleapis.com
    gcloud services enable vision.googleapis.com
    gcloud services enable translate.googleapis.com
    gcloud services enable texttospeech.googleapis.com

Create a Service Account to access the Google Cloud APIs when testing locally:

    gcloud iam service-accounts create gcp-ai-demo \
    --display-name "GCP AI Demo Service Account"

Give your newly created Service Account appropriate permissions:

    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member serviceAccount:gcp-ai-demo@${PROJECT_ID}.iam.gserviceaccount.com \
    --role roles/owner

After creating your Service Account, create a Service Account key:

    gcloud iam service-accounts keys create ~/key.json --iam-account \
    gcp-ai-demo@${PROJECT_ID}.iam.gserviceaccount.com

Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to where
you just put your Service Account key:

    export GOOGLE_APPLICATION_CREDENTIALS="/home/${USER}/key.json"

## Running locally

Create a virtual environment and install dependencies:

    virtualenv -p python3 env
    source env/bin/activate
    pip install -r requirements.txt

Create a Cloud Storage bucket. It is recommended that you name it the same as
your project ID:

    gsutil mb gs://${PROJECT_ID}

Set the environment variable `CLOUD_STORAGE_BUCKET`:

    export CLOUD_STORAGE_BUCKET=${PROJECT_ID}

Start your application locally:

    python main.py

Visit `localhost:8080` to view your application running locally. Press `Control-C`
on your command line when you are finished.

When you are ready to leave your virtual environment:

    deactivate

## Deploying to App Engine

Open `app.yaml` and replace <your-cloud-storage-bucket> with the name of your
Cloud Storage bucket.

Deploy your application to App Engine using `gcloud`. Please note that this may
take several minutes.

    gcloud app deploy

Visit `https://[YOUR_PROJECT_ID].appspot.com` to view your deployed application.
