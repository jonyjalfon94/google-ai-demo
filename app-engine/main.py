import logging, os, random

from flask import Flask, redirect, render_template, request
from google.cloud import datastore
from google.cloud import vision
import google.cloud.translate_v2 as translate
import google.cloud.texttospeech as tts
# from PIL import Image, ImageDraw, ImageFont
from memefy import Meme
from helpers import StorageHelpers
import requests
from requests.structures import CaseInsensitiveDict
from bs4 import BeautifulSoup


# Define variables
CLOUD_STORAGE_BUCKET = os.environ.get("CLOUD_STORAGE_BUCKET")

# Initialize clients
datastore_client = datastore.Client()
vision_client = vision.ImageAnnotatorClient()
tts_client = tts.TextToSpeechClient()
translate_client = translate.Client()
helpers = StorageHelpers()

# Initialize app
app = Flask(__name__)

# Render HTML template
@app.route("/")
def homepage():
    # Use the Cloud Datastore client to fetch information from Datastore about
    # each photo.
    query = datastore_client.query(kind="Memes")
    image_entities = list(query.fetch())
    # Return a Jinja2 HTML template and pass in image_entities as a parameter.
    return render_template("homepage.html", image_entities=image_entities, form_error=False)  

# Submit image to Google Cloud Storage
@app.route("/upload_photo", methods=["GET", "POST"])
def upload_photo():
    photo = request.files["file"]
    blob = helpers.upload_asset_to_bucket(photo, photo.filename, content_type="image/jpeg")
    # The kind for the new entity.
    kind = "Memes"
    # Create the Cloud Datastore key for the new entity.
    key = datastore_client.key(kind, photo.filename)
    # Construct the new entity using the key. Set dictionary values for entity
    # keys blob_name, storage_public_url, timestamp, and joy.
    print("Creating Datastore entity")
    entity = datastore.Entity(key)
    entity["original_image_blob"] = photo.filename
    entity["original_image_public_url"] = blob.public_url
    entity["processed"] = False
    datastore_client.put(entity)
    print("Done")
    return redirect("/")

# Image form button handler
@app.route("/process", methods=["GET", "POST"])
def process():
    blob_name = request.form['original_image_blob']
    # Get image and check if it has a caption
    if request.form['action'] == 'Meme':
        caption = "Put a caption next time you press me" if len(request.form['caption']) == 0 else request.form['caption']
        memefy(blob_name, caption)
    elif request.form['action'] == 'Vision API Caption':
        generate_image_caption(blob_name)
    # Get datastore entity for image
    key = datastore_client.key("Memes", blob_name)
    entity = datastore_client.get(key)
    # Return an error if the image selected has no caption
    if "caption" not in entity:
        query = datastore_client.query(kind="Memes")
        image_entities = list(query.fetch())
        return render_template("homepage.html", image_entities=image_entities, form_error="The image you selected does not have a caption. Please add a caption and try again.")
    if request.form['action'] == 'Translate':
        translate_target_lang = request.form['language']
        translate_text(blob_name, translate_target_lang)
    elif request.form['action'] == 'Text-to-Speech':
        text_to_mp3(blob_name)

    # # Redirect to the home page.
    return redirect("/")

# Get quotes from brainyquote.com by web scraping with BeautifulSoup for a given keyword
def getQuotes(keyword):
    quoteArray = []
    base_url = "https://www.brainyquote.com/quotes/keywords/"
    url = base_url + keyword + ".html"
    response_data = requests.get(url).text[:]
    soup = BeautifulSoup(response_data, 'html.parser')
    # loop through the html source code of the website and find specific keys
    for item in soup.find_all("a", class_="b-qt"):
        quote = item.get_text().rstrip()
        if len(quote) < 80:
            quoteArray.append(quote)
    return quoteArray

# Generate image caption using Google Vision API for collecting labels and taking a quote from brainyquote.com
def generate_image_caption(blob_name):
    # Download original image
    original_image_blob = helpers.download_asset_from_bucket(blob_name)
    # Send original image to vision API
    image = vision.Image(source=vision.ImageSource(image_uri=original_image_blob.public_url))
    quotes = []
    for i in range(3):
        labels = vision_client.label_detection(image=image).label_annotations
        for label in labels:
            #Get quotes from the brainyquote.com for each label
            quotes.extend(getQuotes(label.description))
        if  len(quotes) > 0:
            break
        if i == 2 and len(quotes) == 0:
            print(i)
            for label in labels:
                #Get quotes from icanhazdadjoke.com instead
                headers = CaseInsensitiveDict()
                headers["Accept"] = "application/json"
                jokes = requests.get(f"https://icanhazdadjoke.com/search?term={label.description}", headers=headers).json()["results"]
                for joke in jokes:
                    if len(joke["joke"]) < 80:
                        print(joke["joke"])
                        quotes.append(joke["joke"])
    memefy(blob_name, random.choice(quotes))

# Uses PIL to write a caption on top of the image
def memefy(file_name, caption):
  # Download file
  original_image_blob = helpers.download_asset_from_bucket(file_name)
  # Detect caption language
  detected_lang = translate_client.detect_language(caption)
  # Generate meme
  meme = Meme(caption, helpers.asset_download_location, detected_lang['language'])
  img = meme.draw()
  if img.mode in ("RGBA", "P"):   #Without this the code can break sometimes
      img = img.convert("RGB")
  img.save('captioned_image.jpg', optimize=True, quality=80)
  # Upload meme to bucket
  upload_image_blob = "processed/" + original_image_blob.name
  meme_blob = helpers.upload_asset_to_bucket("captioned_image.jpg", upload_image_blob, content_type="image/jpeg")
  # Update image entity from datastore
  key = datastore_client.key("Memes", file_name)
  entity = datastore_client.get(key)
  for prop in entity:
      entity[prop] = entity[prop]
  entity["processed_image_public_url"] = meme_blob.public_url
  entity["caption"] = caption
  entity["caption_language"] = detected_lang['language']
  entity["processed"] = True
  datastore_client.put(entity)

# Translates text into the target language using Google cloud translate API
def translate_text(file_name, target_lang):
    # Get datastore entity for image
    key = datastore_client.key("Memes", file_name)
    entity = datastore_client.get(key)
    target = target_lang
    # Use Google translate API to translate caption into target language
    translated_text = translate_client.translate(values=entity['caption'], format_="text", target_language=target)
    # Generate meme with translated text
    memefy(file_name, translated_text['translatedText'])

def get_voice(caption_language):
    if caption_language == "fr":
        voice = tts.VoiceSelectionParams(language_code="fr-FR", ssml_gender=tts.SsmlVoiceGender.FEMALE)
        return voice
    elif caption_language == "ru":
        voice = tts.VoiceSelectionParams(language_code="ru-RU", ssml_gender=tts.SsmlVoiceGender.MALE)
        return voice
    elif caption_language == "es":
        voice = tts.VoiceSelectionParams(language_code="es-ES", ssml_gender=tts.SsmlVoiceGender.FEMALE)
        return voice
    elif caption_language == "it":
        voice = tts.VoiceSelectionParams(language_code="it-IT", ssml_gender=tts.SsmlVoiceGender.MALE)
        return voice
    elif caption_language == "iw":
        voice = tts.VoiceSelectionParams(language_code="en-US", ssml_gender=tts.SsmlVoiceGender.NEUTRAL)
        return voice
    # In case the language doesn't match any of the above, chose an english voice
    else:
        voice = tts.VoiceSelectionParams(language_code="en-US", ssml_gender=tts.SsmlVoiceGender.NEUTRAL)
        return voice

# Converts text to an mp3 file using Text to Speech API
def text_to_mp3(blob_name):
    # Get the image caption from its Datastore entity
    key = datastore_client.key("Memes", blob_name)
    entity = datastore_client.get(key)
    # Prepare text to speech input
    synthesis_input = tts.SynthesisInput(text=entity['caption'])
    # Set voice parameters depending on caption language
    if entity["caption_language"] == "iw":
        synthesis_input = tts.SynthesisInput(text="Sorry, hebrew has no supported voice yet. Try translating again to any of the other languages and press the button again.")
    # Set file format for the response
    audio_config = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.MP3
    )
    # Get the voice parameters
    caption_language = entity["caption_language"]
    voice = get_voice(caption_language=caption_language)
    # Get mp3 file from TTS API
    response = tts_client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    # Change file extension to mp3
    pre, ext = os.path.splitext(blob_name)
    upload_mp3_blob = "audio/" + pre + ".mp3"
    # Upload file
    mp3_blob = helpers.upload_asset_to_bucket(response.audio_content, upload_mp3_blob, content_type="audio/mp3")
    # Need to set previous values before updating entity
    for prop in entity:
        entity[prop] = entity[prop]
    entity["mp3_bucket_url"] = mp3_blob.public_url
    datastore_client.put(entity)

@app.errorhandler(500)
def server_error(e):
    logging.exception("An error occurred during a request.")
    return (
        """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(
            e
        ),
        500,
    )

if __name__ == "__main__":
    # This is used when running locally. Gunicorn is used to run the
    # application on Google App Engine. See entrypoint in app.yaml.
    app.run(host="127.0.0.1", port=8080, debug=True)
