import discord
from discord.ext import tasks, commands
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
import datetime
import re
import alkana

COMMAND_PREFIX = ">"
TOKEN = os.environ['VOICEVOX_TOKEN']

voiceChannel = None #: Optional[VoiceChannel]
readChannelID = 0
base_url = "http://127.0.0.1:50031"
headers = {
    'Content-Type': 'application/json',
}


dict_file = open("read_dict", "r", encoding='utf-8')
greeting_file = open("greeting","r",encoding='utf-8')
dict_file_str = dict_file.read()
print(dict_file_str)
greeting_file_str = greeting_file.read()
print(greeting_file_str)

read_dict = json.loads(dict_file_str)
#あいさつ用の dict 
#user_id -> {'hello':x,'bye':y}
greeting_dict = json.loads(greeting_file_str)
dict_file.close()
greeting_file.close()

def save_dict():
    global read_dict
    dict_file = open("read_dict", 'w', encoding='utf-8')
    dict_file.write(json.dumps(read_dict, ensure_ascii=False, indent=2))
    dict_file.close()

def save_greeting():
    global greeting_dict
    greeting_file = open("greeting","w",encoding='utf-8')
    greeting_file.write(json.dumps(greeting_dict,ensure_ascii=False,indent=2))
    greeting_file.close()

def replace_by_dict(text):
    for word, read in read_dict.items():
        text = text.replace(word, read)
    return text



url_regex = re.compile(r"https?://[\w!?/+\-_~;.,*&@#$%()='[\]]+")

def replace_url(text):
    return url_regex.sub("url", text)

def remove_spoiler(text):
    text = re.sub('\|\|.+?\|\|','',text)
    return text

def remove_custom_emoji(text):
    text = re.sub('<:.+?:.+?>','',text)
    return text

def remove_reply_id(text):
    text = re.sub('<@.+?>','',text)
    return text

english_regex = re.compile(r"([a-zA-Z']+)\s*")

def repl_eng_to_kana(matchobj):
    eng = alkana.get_kana(matchobj.group(1))
    if eng is None:
        return matchobj.group(1)
    else:
        return eng

def replace_english_to_kana(text):
    return english_regex.sub(repl_eng_to_kana, text)

def make_read_text(text):
    text = replace_by_dict(text)
    text = replace_url(text)
    text = remove_spoiler(text)
    text = remove_custom_emoji(text)
    text = replace_english_to_kana(text)
    #text = remove_reply_id(text)
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
    if len(text) >= 100:
        text = '長すぎるよ！'
    temp_file = tempfile.NamedTemporaryFile(suffix='.wav', dir='.', delete=False)
    #temp_file = open("shikkoku.wav", "wb")
    print("tempfile: ", temp_file.name)
    create_voice(text, temp_file)
    print("push", temp_file.name)
    que.put(temp_file)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# disconnect if bot has already connected to vc.
async def disconnect():
    global voiceChannel
    global readChannelID
    print("disconnect", readChannelID)
    if readChannelID != 0:
        channel = bot.get_channel(readChannelID)
        await channel.send('おやすみ～')
        await voiceChannel.disconnect()
        voiceChannel = None
        readChannelID = 0

# connect to vc. if bot has already connected to vc, bot disconnect from it.
async def connect(message):
    global voiceChannel
    global readChannelID
    await disconnect()
    readChannelID = message.channel.id
    voiceChannel = await VoiceChannel.connect(message.author.voice.channel)
    print(readChannelID)
    await message.channel.send('おはよ！')

def is_connected():
    global voiceChannel
    return voiceChannel is not None

def read_name(member):
    return member.display_name
    #if member.nick is None:
    #    return member.name
    #else:
    #    return member.nick

@bot.command()
async def con(ctx):
    await connect(ctx.message)
    play_voice("おはようございます")

@bot.command()
async def dc(ctx):
    await disconnect()


@bot.command()
async def add(ctx, before, after):
    global read_dict
    read_dict[before] = after
    save_dict()
    voice_msg = make_read_text(f"{after}、覚えました")
    play_voice(voice_msg)

@bot.command()
async def rem(ctx, before):
    global read_dict
    read_dict.pop(before)
    save_dict()
    voice_msg = make_read_text(f"これからは、{before}って読むね")
    play_voice(voice_msg)

# >hel @user hello 
@bot.command()
async def hel(ctx,after):
    global greeting_dict
    user_id = str(ctx.author.id)
    if user_id not in greeting_dict:
        greeting_dict[user_id] = dict()
    greeting_dict[user_id]['hello'] = after
    save_greeting()
    name = read_name(ctx.author)
    print(ctx.author)
    voice_msg = make_read_text(f"{name}さん、次会ったときは、{after}って言うね。")
    play_voice(voice_msg)

@bot.command()
async def bye(ctx,after):
    global greeting_dict
    user_id = str(ctx.author.id)
    if user_id not in greeting_dict:
        greeting_dict[user_id] = dict()
    greeting_dict[user_id]['bye'] = after
    save_greeting()
    name = read_name(ctx.author)
    voice_msg = make_read_text(f"{name}さん、部屋を出たときは、{after}と伝えるね。")
    play_voice(voice_msg)

@bot.listen()
async def on_message(message):
    global readChannelID

    if message.author.bot or message.content[0].startswith(COMMAND_PREFIX):
        return

    if is_connected() and message.channel.id == readChannelID:
        name = read_name(message.author)
        content = message.clean_content
        print(content)
        content = make_read_text(content)
        if content != '':
            voice_msg = f"{name} {content}"
            play_voice(voice_msg)

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
    if is_connected() and after.channel is None and is_connected_channel(before.channel):
        # check number of member
        print(len(before.channel.members))
        if len(before.channel.members) == 1:
            # disconnect from connected channel
            await disconnect()    
    if is_connected() and before.channel is None and is_connected_channel(after.channel):
        # connecting
        name = read_name(member)
        hello = greeting_dict.get(str(member.id),dict()).get('hello','こんにちは')
        voice_msg = f"{name} {hello}"
        play_voice(voice_msg)
    if is_connected() and after.channel is None and is_connected_channel(before.channel):
        # disconnecting
        name = read_name(member)
        bye = greeting_dict.get(str(member.id),dict()).get('bye','またねー')
        voice_msg = f"{name} {bye}"
        play_voice(voice_msg)
        
sleep_decl_pattern = re.compile(r"(\d+)時に")

def get_sleep_decl(nick):
    if nick is not None:
        m = sleep_decl_pattern.match(nick)
        if m is not None:
            h = int(m.group(1))
            if h == 12:
                h = 0
            return h
        else:
            None
    else:
        return None

@tasks.loop(seconds=60)
async def check_sleep():
    global voiceChannel
    if not is_connected():
        return
    dt_now = datetime.datetime.now()
    print(dt_now)
    if dt_now.minute == 59 or dt_now.minute == 30:
        hour = (dt_now.hour + 1) % 24
        print(hour, "check")
        for member in voiceChannel.channel.members:
            decl_hour = get_sleep_decl(member.nick)
            print(decl_hour, member.name)
            print(decl_hour == hour)
            # encourge
            if decl_hour == (dt_now.hour + 1) % 24 and dt_now.minute == 59:
                name = member.name
                voice_msg = f"{name}さん ねないの"
                play_voice(voice_msg)
            if decl_hour == dt_now.hour and dt_now.minute == 30:
                name = member.name
                voice_msg = f"{name}さん ねてないじゃん！ ねようね"
                play_voice(voice_msg)

@bot.event
async def on_ready():
    print('on_ready')

check_sleep.start()
bot.run(TOKEN)
