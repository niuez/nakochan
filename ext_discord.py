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
from typing import Optional, Union

TOKEN = os.environ['VOICEVOX_TOKEN']

voiceChannel = None #: Optional[VoiceChannel]
readChannelID = 0
base_url = "http://127.0.0.1:50031"
headers = {
    'Content-Type': 'application/json',
}

dict_file = open("read_dict", "r", encoding='utf-8')
dict_file_str = dict_file.read()
print(dict_file_str)
read_dict = json.loads(dict_file_str)
dict_file.close()

def save_dict():
    global read_dict
    dict_file = open("read_dict", 'w', encoding='utf-8')
    dict_file.write(json.dumps(read_dict, ensure_ascii=False, indent=2))
    dict_file.close()

def replace_by_dict(text):
    for word, read in read_dict.items():
        text = text.replace(word, read)
    return text

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

# disconnect if bot has already connected to vc.
async def disconnect(message):
    global voiceChannel
    global readChannelID
    if voiceChannel != 0:
        await message.channel.send('おやすみ～')
        await voiceChannel.disconnect()
        voiceChannel = None
        readChannelID = 0

# connect to vc. if bot has already connected to vc, bot disconnect from it.
async def connect(message):
    global voiceChannel
    global readChannelID
    disconnect(message)
    readChannelID = message.channel.id
    voiceChannel = await VoiceChannel.connect(message.author.voice.channel)
    print(readChannelID)
    await message.channel.send('おはよ！')

def is_connected():
    global voiceChannel
    return voiceChannel is not None

def read_name(member):
    if member.nick is None:
        return member.name
    else:
        return member.nick

@bot.command()
async def con(ctx):
    await connect(ctx.message)

@bot.command()
async def dc(ctx):
    await disconnect(ctx.message)


@bot.command()
async def add(ctx, before, after):
    global read_dict
    read_dict[before] = after
    save_dict()

@bot.command()
async def rem(ctx, before):
    global read_dict
    read_dict.pop(before)
    save_dict()

@bot.event
async def on_message(message):
    global readChannelID

    if message.author.bot:
        return
    await bot.process_commands(message)

    if is_connected() and message.channel.id == readChannelID:
        name = read_name(message.author)
        content = message.content
        voice_msg = f"{name} {content}"
        play_voice(replace_by_dict(voice_msg))

def is_connected_channel(channel):
    global voiceChannel
    if channel is None:
        return False
    elif channel.id == voiceChannel.channel.id:
        return True
    else:
        return False

@bot.event
async def on_voice_state_update(member, before, after):
    if not is_connected():
        return
    if is_connected_channel(before.channel) or is_connected_channel(after.channel):
        if before.channel is None and is_connected_channel(after.channel):
            # connecting
            name = read_name(member)
            voice_msg = f"{name} こんにちは"
            play_voice(voice_msg)
        if after.channel is None and is_connected_channel(before.channel):
            # disconnecting
            name = read_name(member)
            voice_msg = f"{name} またねー"
            play_voice(voice_msg)
        

@bot.event
async def on_ready():
    print('on_ready')

bot.run(TOKEN)