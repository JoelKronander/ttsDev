import streamlit as st
import asyncio
import elevenlabs
from tempfile import NamedTemporaryFile
from pydub import AudioSegment
import io
from openai import AsyncOpenAI, OpenAI
from pathlib import Path
from typing import List

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


async def text2speect_openai_single_voice(text, voice, client):
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
        tasks.append(text2speect_openai_single_voice(text, voice, client))
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
    keys = ['session_id', 'openai_api_key', 'elevenlabs_api_key', 'input_text']
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None

initialize_session()
st.session_state.openai_selected_voices = []
st.session_state.elevenlabs_selected_voices = []
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
    elevenlab_voices = [v.name for v in elevenlabs.voices()]
    for voice in elevenlab_voices:
        st.session_state.elevenlabs_selected_voices.append([voice, st.sidebar.checkbox(voice, value=False)])

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

    else:
        st.error("Please enter some text to generate text to speech from.")
