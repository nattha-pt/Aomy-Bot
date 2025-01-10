import discord
import asyncio
import json
import os
import re
import random
import yt_dlp
from discord.ext import commands, tasks
from discord.ui import Button, View
from collections import deque
from dotenv import load_dotenv

FAVORITES_FILE = 'favorites.json'

# โหลด environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ตรวจสอบว่า TOKEN ถูกตั้งค่าหรือไม่
if TOKEN is None:
    print("Error: DISCORD_TOKEN is not set in .env")
    exit(1)

# กำหนด intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

# สร้าง bot
bot = commands.Bot(command_prefix='.', intents=intents)

@tasks.loop(minutes=5.0)
async def check_voice_activity():
    for guild in bot.guilds:
        if guild.voice_client:
            if len(guild.voice_client.channel.members) == 1 and guild.voice_client.channel.members[0] == guild.voice_client.user:
                await guild.voice_client.disconnect()
                print(f"Disconnected from {guild.voice_client.channel.name} due to inactivity.")

@bot.event
async def on_ready():
    if bot.user:
        print(f'Bot is online as {bot.user.name}')
    else:
        print('Bot user is not defined')
    check_voice_activity.start()

# ------------------------------------------------- MUSIC CONTROL -------------------------------------------------- #
class MusicControlView(View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx

    # Group 1: Playback Controls
    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.secondary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await pause(self.ctx)

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await resume(self.ctx)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await next_song(self.ctx)
    
    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.secondary)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await stop(self.ctx)

    # Group 2: Playlist Controls
    @discord.ui.button(label="💽 คิวเพลง", style=discord.ButtonStyle.secondary)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_queue(self.ctx)

    # @discord.ui.button(label="📻 โหมดวิทยุ", style=discord.ButtonStyle.secondary)
    # async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     await interaction.response.defer()
    #     await show_queue(self.ctx)

    @discord.ui.button(label="⭐ เพิ่มในเพลย์ลิสต์", style=discord.ButtonStyle.secondary)
    async def add_favorite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await add_favorite(self.ctx)
    
    @discord.ui.button(label="🎰 สุ่มจากเพลย์ลิสต์", style=discord.ButtonStyle.secondary)
    async def random_favorite_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await random_favorite(self.ctx)

    # Group 3: Control
    @discord.ui.button(label="HELP !", style=discord.ButtonStyle.primary)
    async def show_help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await show_help(self.ctx)

    @discord.ui.button(label="LEAVE", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await leave(self.ctx)

# class RadioControlView(View):
#     def __init__(self, ctx):
#         super().__init__(timeout=None)
#         self.ctx = ctx
    
#     @discord.ui.button(label="↔️ เปลี่ยนหมวดหมู่", style=discord.ButtonStyle.secondary)
#     async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         await interaction.response.defer()
#         await show_queue(self.ctx)
    
#     @discord.ui.button(label="📻 ปิดโหมดวิทยุ", style=discord.ButtonStyle.secondary)
#     async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         await interaction.response.defer()
#         await show_queue(self.ctx)

#     @discord.ui.button(label="HELP !", style=discord.ButtonStyle.primary)
#     async def show_help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         await interaction.response.defer()
#         await show_help(self.ctx)
    
#     @discord.ui.button(label="LEAVE", style=discord.ButtonStyle.danger)
#     async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#         await interaction.response.defer()
#         await leave(self.ctx)
        
# สร้างคิวเพลงสำหรับแต่ละเซิร์ฟเวอร์
music_queues = {}

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

def get_youtube_info(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            return info_dict
    except Exception as e:
        print(f"Error fetching YouTube info: {e}")
        return None

async def play_next(ctx):
    global current_songs
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        next_song = music_queues[ctx.guild.id].popleft()
        await play_song(ctx, next_song['url'])
    else:
        message = await ctx.send("ไม่มีเพลงในคิวแล้วค่ะ")
        await asyncio.sleep(3)
        await message.delete()
        if ctx.guild.id in current_songs:
            del current_songs[ctx.guild.id]

current_songs = {}

global playing_message
playing_message = None

async def play_song(ctx, url):
    global current_songs, playing_message
    voice_client = ctx.voice_client
    youtube_info = get_youtube_info(url)
    if youtube_info is None:
        message = await ctx.send("ไม่สามารถดึงข้อมูลเพลงจาก URL นี้ได้ กรุณาตรวจสอบลิงก์อีกครั้ง.")
        await asyncio.sleep(3)
        await message.delete()
        return
    youtube_url = youtube_info['url']
    title = youtube_info['title']
    thumbnail_url = youtube_info['thumbnail']  # สมมติว่า 'thumbnail' เก็บ URL ของรูปปก
    duration = youtube_info['duration']  # สมมติว่า 'duration' เก็บความยาวของคลิป (เป็นวินาที)
    # แปลงความยาวเป็นรูปแบบที่สามารถแสดงได้ (เช่น 4:20 สำหรับ 260 วินาที)
    minutes = duration // 60
    seconds = duration % 60
    duration_formatted = f"{minutes}:{str(seconds).zfill(2)}"  # เช่น "4:20"
    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    if voice_client.is_playing():
        voice_client.stop()
    audio_source = discord.FFmpegPCMAudio(youtube_url, **ffmpeg_options)
    current_songs[ctx.guild.id] = {'title': title, 'url': url}
    voice_client.play(audio_source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
    # สร้าง embed พร้อมลิงก์ในชื่อเพลงและรูปโปรไฟล์ของเพลง
    embed = discord.Embed(
        title="กำลังเล่นเพลง", 
        description=f"[`{title}`]({youtube_url})",  # ชื่อเพลงเป็นลิงก์
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=thumbnail_url)  # เพิ่มรูปโปรไฟล์เพลง
    embed.set_footer(text=f"ความยาว: {duration_formatted}")  # แสดงความยาวใน footer
    # ลบข้อความเดิมและส่งข้อความใหม่
    if playing_message:
        try:
            await playing_message.delete()  # ลบข้อความเดิม
        except discord.NotFound:
            pass  # กรณีที่ข้อความถูกลบไปแล้ว
    # ส่งข้อความใหม่
    playing_message = await ctx.send(embed=embed)
    # เพิ่มปุ่มควบคุมการเล่นเพลง
    view = MusicControlView(ctx)
    await playing_message.edit(view=view)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # ตรวจสอบว่าเป็น URL ของ YouTube หรือไม่
    youtube_url_pattern = re.compile(r'https?://(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/.+')
    if youtube_url_pattern.match(message.content):
        print(f"Received YouTube URL: {message.content}")
        # เรียกใช้ฟังก์ชัน play โดยตรงจากคำสั่งที่กำหนด
        command = bot.get_command('play')
        if command:
            # สร้าง context จำลอง
            ctx = await bot.get_context(message)
            await command.callback(ctx, url=message.content)
            print("Invoking play command directly.")
        else:
            print("Command 'play' not found.")
    await bot.process_commands(message)

@bot.command(name='เล่น', aliases=['play', 'p'])
async def play(ctx, url: str):
    if not ctx.author.voice:
        message = await ctx.send("คุณต้องอยู่ในช่องเสียงเพื่อใช้คำสั่งนี้")
        await asyncio.sleep(3)
        await message.delete()
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)
    if ctx.guild.id not in music_queues:
        music_queues[ctx.guild.id] = deque()
    youtube_info = get_youtube_info(url)
    if youtube_info is None:
        message = await ctx.send("ไม่สามารถดึงข้อมูลเพลงจาก URL นี้ได้ กรุณาตรวจสอบลิงก์อีกครั้ง")
        await asyncio.sleep(3)
        await message.delete()
        return
    title = youtube_info.get('title', 'เพลงไม่รู้จัก')
    if ctx.voice_client.is_playing():
        music_queues[ctx.guild.id].append({'url': url, 'title': title})
        message = await ctx.send(f"เพิ่มเพลง '{title}' ลงในคิวแล้ว")
        await asyncio.sleep(3)
        await message.delete()
    else:
        await play_song(ctx, url)

@bot.command(name='ต่อไป', aliases=['next', 'n'])
async def next_song(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    else:
        message = await ctx.send("ไม่มีเพลงที่กำลังเล่นอยู่ค่ะ")
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='คิว', aliases=['queue', 'q'])
async def show_queue(ctx):
    if ctx.guild.id in music_queues and music_queues[ctx.guild.id]:
        queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(music_queues[ctx.guild.id])])
        embed = discord.Embed(title="คิวเพลง", description=queue_list, color=discord.Color.green())
        message = await ctx.send(embed=embed)
        await asyncio.sleep(3)
        await message.delete()
    else:
        message = await ctx.send("ไม่มีเพลงในคิวค่ะ")
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='หยุด', aliases=['stop', 's'])
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        message = await ctx.send('หยุดเล่นเพลงชั่วคราว หากต้องการเล่นเพลงต่อ ให้พิมพ์คำสั่ง "เล่นต่อ"')
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='เล่นต่อ', aliases=['continue', 'cn'])
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        message = await ctx.send("กำลังเล่นเพลงต่อ")
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='ปิดเพลง', aliases=['clear', 'clr'])
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()
        message = await ctx.send("ปิดเพลงและล้างคิวแล้ว")
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='ลบเพลง', aliases=['remove', 'rm'])
async def remove_song(ctx, song_number: int):
    if ctx.guild.id not in music_queues or not music_queues[ctx.guild.id]:
        message = await ctx.send("คิวเพลงว่างอยู่ ไม่สามารถลบเพลงได้ค่ะ")
        await asyncio.sleep(3)
        await message.delete()
    if song_number < 1 or song_number > len(music_queues[ctx.guild.id]):
        message = await ctx.send(f"หมายเลขเพลงไม่ถูกต้อง กรุณาระบุหมายเลขระหว่าง 1 และ {len(music_queues[ctx.guild.id])}")
        await asyncio.sleep(3)
        await message.delete()
    # ลบเพลงจากคิวที่ตำแหน่งที่กำหนด
    if song_number == 1:
        removed_song = music_queues[ctx.guild.id].popleft()
    else:
        removed_song = music_queues[ctx.guild.id][song_number - 1]
        music_queues[ctx.guild.id].remove(removed_song)
    # ตรวจสอบว่า removed_song ไม่เป็น None ก่อนใช้
    if removed_song is not None:
        message = await ctx.send(f"เพลง '{removed_song['title']}' ถูกลบจากคิวแล้ว")
        await asyncio.sleep(3)
        await message.delete()
    else:
        message = await ctx.send("ไม่พบเพลงที่ต้องการลบ")
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='ออกไป', aliases=['leave', 'l'])
async def leave(ctx):
    global playing_message
    if ctx.voice_client:
        await ctx.voice_client.disconnect()  # บอทออกจากห้องเสียง
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()  # เคลียร์คิวเพลง
    # ลบ playing_message ถ้ามี
    if playing_message:
        try:
            await playing_message.delete()
        except discord.NotFound:
            pass  # กรณีที่ข้อความถูกลบไปแล้ว
    # ส่งข้อความออกจากช่องเสียงและลบมันหลังจาก 3 วินาที
    message = await ctx.send("ออมมี่ออกจากช่องเสียงแล้ว 😢")
    await asyncio.sleep(3)
    await message.delete()

@bot.command(name='คู่มือ', aliases=['assist', 'guide', 'h'])
async def show_help(ctx):
    embed = discord.Embed(title="📕 คู่มือการรับมือพี่ออม", description="คำสั่งที่ใช้ได้สำหรับการควบคุมเพลงในห้องเสียง",)
    embed.add_field(name="> `เล่น, play, p <ลิงก์>`", value="เล่นเพลงจากยูทูป", inline=False)
    embed.add_field(name="> `ต่อไป, next, n`", value="เล่นเพลงถัดไปจากคิว", inline=False)
    embed.add_field(name="> `ลบเพลง, remove, rm <หมายเลข>`", value="ลบเพลงจากคิวตามหมายเลขในคิว", inline=False)
    embed.add_field(name="> `คิว, queue, q`", value="แสดงเพลงทั้งหมดในคิว", inline=False)
    embed.add_field(name="> `ปิดเพลง, clear, clr`", value="หยุดเล่นเพลงและล้างคิวทั้งหมด", inline=False)
    embed.add_field(name="> `หยุด, stop, s`", value="หยุดเล่นเพลงชั่วคราว", inline=False)
    embed.add_field(name="> `เล่นต่อ, continue, con`", value="เล่นเพลงต่อจากที่หยุดก่อนหน้านี้", inline=False)
    embed.add_field(name="> `ออกไป, leave, l`", value="ออกจากช่องเสียง", inline=False)
    embed.add_field(name="💡 ตัวอย่างการใช้งาน", value="`.p https://www.youtube.com/xxx/?`", inline=False)
    embed.add_field(name="💥 New! คำสั่งเล่นเพลง", value="สามารถวางลิงก์โดยไม่ต้องใช้ คำสั่ง `.p` ได้แล้วนะ", inline=False)
    embed.set_image(url="https://embed.pixiv.net/artwork.php?illust_id=90077277&mdate=1621870500")
    embed.set_footer(text="หากคุณมีคำถามเพิ่มเติม โปรดติดต่อผู้ดูแล BOT")
    message = await ctx.send(embed=embed)
    await asyncio.sleep(15)
    await message.delete()

# @bot.command(name='พี่ออม', aliases=['aommy'])
# async def next_song(ctx):
#     message = await ctx.send("งานเสร็จหรือยังคะ?")
#     await asyncio.sleep(5)
#     await message.delete()

# นำเข้าเพลงจาก JSON
def load_favorites():
    if not os.path.exists(FAVORITES_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_favorites(favorites):
    with open(FAVORITES_FILE, 'w', encoding="utf-8") as f:
        json.dump(favorites, f, ensure_ascii=False, indent=2)

@bot.command(name='เพิ่มในรายการโปรด')
async def add_favorite(ctx):
    global current_songs
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        message = await ctx.send("ไม่มีเพลงที่กำลังเล่นอยู่ในขณะนี้ค่ะ")
        await asyncio.sleep(3)
        await message.delete()
        return
    if ctx.guild.id not in current_songs:
        message = await ctx.send("ไม่พบข้อมูลเพลงปัจจุบันค่ะ")
        await asyncio.sleep(3)
        await message.delete()
        return
    current_song = current_songs[ctx.guild.id]
    favorites = load_favorites()
    new_favorite = {'title': current_song['title'], 'url': current_song['url']}
    if new_favorite not in favorites:
        favorites.append(new_favorite)
        save_favorites(favorites)
        message = await ctx.send(f"เพิ่ม '{current_song['title']}' ในรายการโปรดแล้วค่ะ")
        await asyncio.sleep(3)
        await message.delete()
    else:
        message = await ctx.send(f"'{current_song['title']}' มีอยู่ในรายการโปรดแล้วค่ะ")
        await asyncio.sleep(3)
        await message.delete()

@bot.command(name='เล่นเพลงแบบสุ่มจากรายการโปรด')
async def random_favorite(ctx):
    favorites = load_favorites()
    if not favorites:
        message = await ctx.send("ยังไม่มีเพลงในรายการโปรดค่ะ")
        await asyncio.sleep(3)
        await message.delete()
        return
    # สุ่มเพลงจากรายการโปรด
    random.shuffle(favorites)
    selected_songs = favorites[:10]  # เลือกสุ่มไม่เกิน 10 เพลง
    # เพิ่มเพลงที่เลือกลงในคิว
    for song in selected_songs:
        if ctx.guild.id not in music_queues:
            music_queues[ctx.guild.id] = deque()
        music_queues[ctx.guild.id].append(song)
    # เล่นเพลงถ้ายังไม่มีเพลงเล่นอยู่
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        await play_next(ctx)
    message = await ctx.send(f"เพิ่ม {len(selected_songs)} เพลงจากรายการโปรดลงในคิวแล้วค่ะ")
    await asyncio.sleep(3)
    await message.delete()

# END OF MUSIC CONTROL

# -------------------------------------------- WELCOME/GOODBYE MESSAGE -------------------------------------------- #
@bot.event
async def on_member_join(member):
    # ช่องที่ใช้ส่ง Welcome Message
    channel = bot.get_channel(952617523847778394)
    
    # กำหนด Role ที่ต้องการให้สมาชิกใหม่
    guild = member.guild
    role = guild.get_role(878607127126634496)
    
    if role:  # ตรวจสอบว่าเจอ Role หรือไม่
        await member.add_roles(role)  # เพิ่ม Role ให้กับสมาชิกใหม่

    # สร้างข้อความต้อนรับ
    if channel:
        embed = discord.Embed(
            title="\u200B\n😤 **มุ่ ง สู ด ด ม ก า ว แ ล ะ ข อ ง เ ห ล ว** 🍻",
            description=f"ยินดีต้อนรับ {member.mention}\nนักผจญภัยมือใหม่ {role.mention} เข้าสู่กิลด์!",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.avatar.url)
        channel_id = 1264512768351141901  # ใส่ channel ID ที่คุณต้องการลิงก์
        embed.add_field(
            name="\u200B\n📃 **คู่มือนักผจญภัย**",
            value=f"กรุณาอ่านกฎและปฏิบัติตามให้เรียบร้อย \n<#{channel_id}>\n",
            inline=False
        )

        embed.add_field(
            name="\n💬 **เข้าร่วมการสนทนา**",
            value="มาพูดคุยและทำความรู้จักกับเพื่อนๆ ในห้องแชตต่างๆ!",
            inline=False
        )
        embed.set_footer(
            text="\n🎉 เราหวังว่าคุณจะมีช่วงเวลาที่ดีในกิลด์ของเรา! 🎉"
        )
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(952617523847778394)
    if channel:
        embed = discord.Embed(
            title="👋 👋 👋 👋 👋 👋 👋",
            description=f"{member.name} ได้ลาออกจากกิลด์นักผจญภัย {member.guild.name}!",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.avatar.url)
        await channel.send(embed=embed)

# END WELCOME/GOODBYE MESSAGE

bot.run(TOKEN)