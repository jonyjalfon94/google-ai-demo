import logging, os, math, io, random

from flask import Flask, redirect, render_template, request
from google.cloud import datastore
from google.cloud import vision
import google.cloud.translate_v2 as translate
import google.cloud.texttospeech as tts
from PIL import Image, ImageDraw, ImageFont
from memefy import Meme
from helpers import StorageHelpers

CLOUD_STORAGE_BUCKET = os.environ.get("CLOUD_STORAGE_BUCKET")
app = Flask(__name__)

@app.route("/")
def homepage():
    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()
    # Use the Cloud Datastore client to fetch information from Datastore about
    # each photo.
    query = datastore_client.query(kind="Faces")
    image_entities = list(query.fetch())
    # Return a Jinja2 HTML template and pass in image_entities as a parameter.
    return render_template("homepage.html", image_entities=image_entities)  

@app.route("/upload_photo", methods=["GET", "POST"])
def upload_photo():
    photo = request.files["file"]
    helpers = StorageHelpers()
    blob = helpers.upload_asset_to_bucket(photo, photo.filename, content_type="image/jpeg")
    datastore_client = datastore.Client()
    # The kind for the new entity.
    kind = "Faces"
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

@app.route("/process", methods=["GET", "POST"])
def process():
    blob_name = request.form['original_image_blob']

    if request.form['action'] == 'Meme':
        print("Meme")
        caption = "Put a caption next time you press me" if len(request.form['caption']) == 0 else request.form['caption']
        memefy(blob_name, caption)
    elif request.form['action'] == 'Vision':
        print("Vision")
        highlight_faces(blob_name)
    elif request.form['action'] == 'Translate':
        translate_target_lang = request.form['language']
        print(translate_target_lang)
        translate_text(blob_name, translate_target_lang)
    elif request.form['action'] == 'Text-to-Speech':
        print("Text to Speech")
        text_to_mp3(blob_name)

    # # Redirect to the home page.
    return redirect("/")

def highlight_faces(blob_name):
    # Initialize storage helpers class
    helpers = StorageHelpers()
    # Download original image
    original_image_blob = helpers.download_asset_from_bucket(blob_name)
    original_image = helpers.asset_download_location
    # Send original image to vision API
    client = vision.ImageAnnotatorClient()
    image = vision.Image(source=vision.ImageSource(image_uri=original_image_blob.public_url))
    faces = client.face_detection(image=image, max_results=100).face_annotations
    # Open original image with PIL to draw on top of it
    im = Image.open(original_image)
    draw = ImageDraw.Draw(im)
    # Sepecify the font-family and the font-size
    font_joyscore = ImageFont.truetype("Roboto-Regular.ttf", 38)
    font = ImageFont.truetype("Roboto-Regular.ttf", 24)
    # Define total joy score
    joy_score = 0
    # Define joy likelihood counters for each possible value.
    unknown = 0
    very_unnlikely = 0
    unlikely = 0
    possible = 0
    likely = 0
    very_likely = 0
    for face in faces:
        box = [(vertex.x, vertex.y)
               for vertex in face.bounding_poly.vertices]
        draw.line(box + [box[0]], width=5, fill='#0dff00')
        # Place the confidence value/score of the detected faces above the
        # detection box in the output image
        draw.text(((face.bounding_poly.vertices)[0].x,
                   (face.bounding_poly.vertices)[0].y - 30),
                  str(format(face.detection_confidence, '.3f')) + '%',
                  fill='#00ff00',
                  font=font)
        # Joy score is calculated by adding all joy likelihoods together
        if str(face.joy_likelihood) == 'Likelihood.VERY_UNLIKELY':
            very_unnlikely += 1
        elif str(face.joy_likelihood) == 'Likelihood.UNLIKELY':
            unlikely += 2
        elif str(face.joy_likelihood) == 'Likelihood.POSSIBLE':
            possible += 3
        elif str(face.joy_likelihood) == 'Likelihood.LIKELY':
            likely += 4
        elif str(face.joy_likelihood) == 'Likelihood.VERY_LIKELY':
            very_likely += 5
        else:
            unknown += 1
    # Calculate Joy Score
    joy_score = math.ceil((likely + very_unnlikely + possible + unlikely + very_likely) / (len(faces)))
    print('Joy Score: {}'.format(joy_score))
    draw.text((0,0),
              "Joy Score: {} out of 5".format(joy_score),
              fill='#0dff00',
              font=font_joyscore)
    im.save("tmp.jpeg")
    # Define process image blob name
    upload_image_blob = "processed/" + original_image_blob.name
    # Upload image to bucket
    blob = helpers.upload_asset_to_bucket("tmp.jpeg", blob_name=upload_image_blob, content_type="image/jpeg")
    print("Image was uploaded") 
    # Create a Cloud Datastore client.
    datastore_client = datastore.Client()
    # The kind for the new entity.
    kind = "Faces"
    # The name/ID for the new entity.
    name = blob_name
    # Create the Cloud Datastore key for the new entity.
    key = datastore_client.key(kind, name)
    # Construct the new entity using the key. Set dictionary values for entity
    # keys blob_name, storage_public_url, timestamp, and joy.
    entity = datastore.Entity(key)
    entity["original_image_blob"] = blob_name
    entity["processed_image_public_url"] = blob.public_url
    entity["joy_score"] = joy_score
    entity["ammount_of_faces"] = len(faces)
    entity["processed"] = True
    datastore_client.put(entity)
    print("Datastore entity added")

def memefy(file_name, caption="stam"):
  helpers = StorageHelpers()
  original_image = helpers.asset_download_location
  original_image_blob = helpers.download_asset_from_bucket(file_name)
  # Detect caption language
  translate_client = translate.Client()
  detected_lang = translate_client.detect_language(caption)
  print(detected_lang['language'])
  meme = Meme(caption, original_image, detected_lang['language'])
  img = meme.draw()
  if img.mode in ("RGBA", "P"):   #Without this the code can break sometimes
      img = img.convert("RGB")
  img.save('captioned_image.jpg', optimize=True, quality=80)
  upload_image_blob = "processed/" + original_image_blob.name
  meme_blob = helpers.upload_asset_to_bucket("captioned_image.jpg", upload_image_blob, content_type="image/jpeg")
  datastore_client = datastore.Client()
  # Fetch the current date / time.
  kind = "Faces"
  # The name/ID for the new entity.
  name = file_name
  # Create the Cloud Datastore key for the new entity.
  key = datastore_client.key(kind, name)
  # Construct the new entity using the key. Set dictionary values for entity
  # keys blob_name, storage_public_url, timestamp, and joy.
  entity = datastore.Entity(key)
  entity["processed_image_public_url"] = meme_blob.public_url
  entity["original_image_blob"] = original_image_blob.name
  entity["caption"] = caption
  entity["caption_language"] = detected_lang['language']
  entity["processed"] = True
  datastore_client.put(entity)
  print("Datastore entity added")

def translate_text(file_name, target_lang):
    helpers = StorageHelpers()
    helpers.download_asset_from_bucket(f"processed/{file_name}")
    client = vision.ImageAnnotatorClient()
    with io.open(helpers.asset_download_location, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    text =  texts[0].description
    print(text)
    translate_client = translate.Client()
    target = target_lang
    translated_text = translate_client.translate(values=text, format_="text", target_language=target)
    print(translated_text['translatedText'])
    memefy(file_name, translated_text['translatedText'])

def text_to_mp3(blob_name):
    datastore_client = datastore.Client()
    # Use the Cloud Datastore client to fetch information from Datastore about
    # each photo.
    key = datastore_client.key('Faces', blob_name)
    entity = datastore_client.get(key)
    synthesis_input = tts.SynthesisInput(text=entity['caption'])
    client = tts.TextToSpeechClient()
    voices = client.list_voices(language_code=entity["caption_language"])
    if entity["caption_language"] == "en":
        voice = tts.VoiceSelectionParams(language_code="en-US", ssml_gender=tts.SsmlVoiceGender.NEUTRAL)
    elif entity["caption_language"] == "fr":
        voice = tts.VoiceSelectionParams(language_code="fr-FR", ssml_gender=tts.SsmlVoiceGender.FEMALE)
    elif entity["caption_language"] == "ru":
        voice = tts.VoiceSelectionParams(language_code="ru-RU", ssml_gender=tts.SsmlVoiceGender.MALE)
    elif entity["caption_language"] == "es":
        voice = tts.VoiceSelectionParams(language_code="es-ES", ssml_gender=tts.SsmlVoiceGender.FEMALE)
    elif entity["caption_language"] == "it":
        voice = tts.VoiceSelectionParams(language_code="it-IT", ssml_gender=tts.SsmlVoiceGender.MALE)
    elif entity["caption_language"] == "iw":
        synthesis_input = tts.SynthesisInput(text="Sorry, hebrew has no supported voice yet. Try translating again to any of the other languages and press the button again.")
        voice = tts.VoiceSelectionParams(language_code="en-US", ssml_gender=tts.SsmlVoiceGender.NEUTRAL)

    audio_config = tts.AudioConfig(
        audio_encoding=tts.AudioEncoding.MP3
    )
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    with open("output.mp3", "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)
        print('Audio content written to file "output.mp3"')
    helpers = StorageHelpers()
    pre, ext = os.path.splitext(blob_name)
    upload_mp3_blob = "audio/" + pre + ".mp3"
    mp3_blob = helpers.upload_asset_to_bucket("output.mp3", upload_mp3_blob, content_type="audio/mp3")
    # Need to set previous values for updating entity
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
