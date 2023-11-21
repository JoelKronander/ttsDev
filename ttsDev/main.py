import streamlit as st
import asyncio
import elevenlabs
from lmnt.api import Speech as LmntSpeech
from tempfile import NamedTemporaryFile
from pydub import AudioSegment
import io
from openai import AsyncOpenAI, OpenAI
from pathlib import Path
from typing import List
import datetime
import uuid

st.set_page_config(
    page_title="ttsDev",
    page_icon="🎙",
    layout="centered",
    initial_sidebar_state="auto",
)


def eleven_labs_text_2_speech(text: str, voice: elevenlabs.Voice):
    # Generate audio without chunking
    audio = elevenlabs.generate(text=text, voice=voice, model="eleven_multilingual_v2")
    return audio


async def lmnt_text_2_speech(text: str, voice: str):
    async with LmntSpeech(st.session_state.lmnt_api_key) as speech:
        response = await speech.synthesize(text, voice)
        return response["audio"]


async def lmnt_get_voices():
    async with LmntSpeech(st.session_state.lmnt_api_key) as speech:
        return await speech.list_voices()


async def lmnt_clone_voice(name: str, files: List[str], description: str = None):
    async with LmntSpeech(st.session_state.lmnt_api_key) as speech:
        response = await speech.create_voice(name, False, files, description=description)
        return response


async def text2speech_openai_single_voice(text, voice, client):
    response = await client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text
    )
    with NamedTemporaryFile(suffix=".mp3", delete=True) as temp_file:
        temp_file_path = temp_file.name  # Get the file path
        response.stream_to_file(temp_file_path)  # Use the file path here
        chunk_audio = AudioSegment.from_mp3(temp_file_path)  # Use the file path to load the audio
        # convert to BytesIO object representing the audio 
        buffer = io.BytesIO()
        chunk_audio.export(buffer, format="mp3")
    return buffer


async def text_2_speech_openai(text, voices) -> List[io.BytesIO]:
    if len(text) > 4000:
        raise ValueError("Can't handle longer than 4000 characters")

    client = AsyncOpenAI(api_key=openai_api_key)
    tasks = []
    for voice in voices:
        tasks.append(text2speech_openai_single_voice(text, voice, client))
    chunk_audios = await asyncio.gather(*tasks)

    return chunk_audios

def generate_random_gpt_text(openai_api_key):
    client = OpenAI(api_key=openai_api_key)
    completion = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write a short haiku"},
    ]
    )
    return completion.choices[0].message.content


def initialize_session():
    keys = ['session_id', 'openai_api_key', 'elevenlabs_api_key', 'lmnt_api_key', 'input_text', 'name_of_cloned_voice']
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None


def handle_voice_cloning(clone_func, is_async, api_name):
    voice_cloning_file = st.sidebar.file_uploader(
        "Upload an audio file to create a new voice from voice cloning.", type=["wav"], key=api_name + "_voice_cloning_file"
    )
    if voice_cloning_file:
        name_of_cloned_voice = st.sidebar.text_input("Name of cloned voice", key=api_name + "_name_of_cloned_voice")
        clone_button = st.sidebar.button("Clone voice", key=api_name + "_clone_button")
        if clone_button:
            with NamedTemporaryFile(suffix=".mp3", delete=True) as temp_file:
                temp_file_name = temp_file.name
                with open(temp_file_name, "wb") as f:
                    f.write(voice_cloning_file.read())
                if is_async:
                    asyncio.run(clone_func(name=name_of_cloned_voice+"_"+str(datetime.datetime.now()), files=[temp_file_name], description="Custom voice"))
                else:
                    clone_func(name=name_of_cloned_voice+"_"+str(datetime.datetime.now()), files=[temp_file_name], description="Custom voice")


initialize_session()
st.session_state.openai_selected_voices = []
st.session_state.elevenlabs_selected_voices = []
st.session_state.lmnt_selected_voices = []
st.title("ttsDev")
st.subheader("Text to speech development tool, that lets you compare different voices from different providers.")

# Sidebar controls
openai_api_key = st.sidebar.text_input("OpenAI API Key")
if openai_api_key.startswith("sk-"):
    st.session_state.openai_api_key = openai_api_key
    for openai_voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
        st.session_state.openai_selected_voices.append([openai_voice, st.sidebar.checkbox(openai_voice, value=True)])
else:
    st.sidebar.warning("Please enter your Open AI key", icon="⚠️")

elevenlabs_api_key = st.sidebar.text_input("Elevenlabs API Key")
if elevenlabs_api_key:
    st.session_state.elevenlabs_api_key = elevenlabs_api_key
    elevenlabs.set_api_key(elevenlabs_api_key)
    handle_voice_cloning(elevenlabs.clone, False, "elevenlabs")
    elevenlab_voices = [v for v in elevenlabs.voices()]
    for voice in elevenlab_voices:
        st.session_state.elevenlabs_selected_voices.append([voice.name, st.sidebar.checkbox(voice.name, key=voice.voice_id, value=False)])

lmnt_api_key = st.sidebar.text_input("LMNT API Key")
if lmnt_api_key:
    st.session_state.lmnt_api_key = lmnt_api_key
    handle_voice_cloning(lmnt_clone_voice, True, "lmnt")
    for voice in asyncio.run(lmnt_get_voices()):
        st.session_state.lmnt_selected_voices.append([voice, st.sidebar.checkbox(voice["name"], key=voice["id"], value=False)])

if st.button("Generate GPT4 blurb"):
    text = generate_random_gpt_text(st.session_state.openai_api_key)
    print(text)
    st.session_state['input_text'] = text

user_input = st.text_area("Enter text for TTS", key='input_text', height=200)

# Submit button
if st.button("Run TTS"):
    if user_input:
        openai_voices_to_generate = [voice[0] for voice in st.session_state.openai_selected_voices if voice[1]]
        audios = asyncio.run(text_2_speech_openai(user_input, openai_voices_to_generate))
        for openai_voice, audio in zip(openai_voices_to_generate, audios):
            s = st.container()
            with s:
                st.subheader(f"OpenAI voice {openai_voice}")
                st.audio(audio, format="audio/mp3")

        elevenlabs_voices_to_generate = [voice[0] for voice in st.session_state.elevenlabs_selected_voices if voice[1]]
        for elevenlabs_voice in elevenlabs_voices_to_generate:
            audio = eleven_labs_text_2_speech(user_input, elevenlabs_voice)
            s = st.container()
            with s:
                st.subheader(f"Elevenlabs voice {elevenlabs_voice}")
                st.audio(audio, format="audio/mp3")

        lmnt_voices_to_generate = [voice[0] for voice in st.session_state.lmnt_selected_voices if voice[1]]
        for lmnt_voice in lmnt_voices_to_generate:
            audio = asyncio.run(lmnt_text_2_speech(user_input, lmnt_voice["id"]))
            s = st.container()
            with s:
                st.subheader(f"LMNT voice {lmnt_voice['name']}")
                st.audio(audio, format="audio/mp3")

    else:
        st.error("Please enter some text to generate text to speech from.")
