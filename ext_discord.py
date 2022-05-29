import discord
from discord.ext import commands
from discord.channel import VoiceChannel
from discord.player import FFmpegPCMAudio
import urllib.request
import urllib.parse
import os.path
import json
import tempfile
import threading, queue
import pathlib
from threading import Event
import os

TOKEN = os.environ['VOICEVOX_TOKEN']

voiceChannel: VoiceChannel 

base_url = "http://127.0.0.1:50031"
headers = {
    'Content-Type': 'application/json',
}

que = queue.Queue()

def play_voice_worker():
    while True:
        temp_file = que.get()
        print("play", temp_file.name)
        #voiceChannel.play(FFmpegPCMAudio(temp_file.name), after = lambda res: temp_file.close())
        #p_abs = pathlib.Path(temp_file.name)
        #p_rel = f"{p_abs.relative_to(pathlib.Path.cwd())}"
        #print(p_rel)
        try:
            event = Event()
            voiceChannel.play(FFmpegPCMAudio(temp_file.name), after = lambda res: event.set())
            print("waiting")
            event.wait()
            print("ok")
            temp_file.close()
            os.remove(temp_file.name)
        finally:
            que.task_done()

threading.Thread(target=play_voice_worker, daemon=True).start()

def create_voice(text, temp_file):
    voice_query_arg = {
        "text": text,
        "speaker": 1,
    }
    voice_query_url = "{}?{}".format(f"{base_url}/audio_query", urllib.parse.urlencode(voice_query_arg))
    print(voice_query_url)
    req = urllib.request.Request(voice_query_url, json.dumps({}).encode(), headers)
    with urllib.request.urlopen(req) as res:
        synthesis_body = res.read()
        print(synthesis_body)
        synthesis_arg = {
            "speaker": 1,
        }
        synthesis_url = "{}?{}".format(f"{base_url}/synthesis", urllib.parse.urlencode(synthesis_arg))
        req = urllib.request.Request(synthesis_url, synthesis_body, headers)
        with urllib.request.urlopen(req) as res:
            print("copy")
            temp_file.write(res.read())

def play_voice(text):
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', dir='.', delete=False)
    #temp_file = open("shikkoku.wav", "wb")
    print("tempfile: ", temp_file.name)
    create_voice(text, temp_file)
    print("push", temp_file.name)
    que.put(temp_file)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=">", intents=intents)

@bot.event
async def on_message(message):
    print("on_message", message.content)
    global voiceChannel

    if message.author.bot:
        return
    if message.content == '!vcon':
        voiceChannel = await VoiceChannel.connect(message.author.voice.channel)
        await message.channel.send('connected')
        return
    elif message.content == '!vdc':
        voiceChannel.stop()
        await message.channel.send('disconnected')
        await voiceChannel.disconnect()
        return

    play_voice(message.content)

@bot.event
async def on_ready():
    print('on_ready')

bot.run(TOKEN)