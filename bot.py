import discord
import os
import sys
import time
import json
from discord.ext import commands,tasks
from modules.models import load_model
from modules.text_generation import generate_reply
import modules.shared as shared



def log(str):
    a=open("log.txt","ab")
    a.write(str.encode())
    a.write('\n'.encode())
    a.close()

intents = discord.Intents.default()
intents.members = True
intents.typing = True
intents.presences = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", help_command=None,intents=intents)

# The message queue
msgqueue=[]

@tasks.loop(seconds=2)
async def thread_reply():
        global msgqueue
        await bot.change_presence(activity=discord.Game(name='Queue: %d'% len(msgqueue)))
        if len(msgqueue)>0:
            message=msgqueue.pop(0)
            await answerMessage(message)

@bot.command()
async def info(ctx):
    await ctx.send(ctx.guild)
    await ctx.send(ctx.author)

@bot.event
async def on_ready() -> None:
    msg=f"Bot {bot.user} waking up."
    print(msg)
    log(msg)
    await bot.change_presence(activity=discord.Game(name="")) 
    thread_reply.start()

@bot.event
async def on_message(message):
    global msgqueue
    if message.author == bot.user:
        return
    botid=("<@%d>" % bot.user.id)
    if message.content.startswith(botid):
        msgqueue.append(message)
        

async def answerMessage(message):
        # Default config values
        temperature= 1.5
        top_p= 0.1
        top_k=40
        max_len=256
        repetition_penalty=1.15
        # Process Message
        botid=("<@%d>" % bot.user.id)
        query = message.content[len(botid):].strip()
        origquery=query
        query=query[:1024] # limit query lenght
        jsonEnd=query.find('}')
        rawpos=query.find('raw')
        if (jsonEnd > rawpos):
            jsonEnd=0 # this is not configuration
        try:
            if (jsonEnd>0): # json config present, parse
                    config=query[:jsonEnd+1]
                    query=query[jsonEnd+1:].strip()
                    config=json.loads(config)
                    if not (config.get('temperature') is None):
                        temperature=float(config['temperature'])
                    if not (config.get('top_p') is None):
                        top_p=float(config['top_p'])
                    if not (config.get('top_k') is None):
                        top_k=int(config['top_k'])
                    if not (config.get('max_len') is None):
                        max_len=int(config['max_len'])
                        if (max_len>512): max_len=512
                    if not (config.get('repetition_penalty') is None):
                        repetition_penalty=float(config['repetition_penalty'])
        except Exception as e:
                msg = f"{message.author.mention} Error parsing the Json config: %s" % str(e)
                log(msg)
                await message.channel.send(msg)
                return

        if (query.startswith('raw ')): # Raw prompt
                query = query[4:]
        else: # Wrap prompt in question
                query ='The answer for "%s" would be: ' % query
        print(origquery)
        async with message.channel.typing():
            try:
                results = generate_reply(query, 
                                        max_new_tokens=max_len, 
                                        do_sample=False, 
                                        temperature=temperature, 
                                        top_p=top_p, 
                                        typical_p=0.1, 
                                        repetition_penalty=repetition_penalty, 
                                        top_k=top_k, 
                                        min_length=0, 
                                        eos_token=None, 
                                        stopping_string=None, 
                                        no_repeat_ngram_size=0,
                                        num_beams=1,
                                        penalty_alpha=0,
                                        length_penalty=1,
                                        early_stopping=False)
            except: 
                msg='Generation error'
                await message.channel.send(msg)
                return
        log("---"+str(origquery))
        
        for result in results:
            msg = f"{message.author.mention} {result[0]}"
            log(msg)
            if len(msg)>1500:
                for i in range(0,len(msg),1500):
                    await message.channel.send(msg[i:i+1500])
            else:
                await message.channel.send(msg)
            break

def main():
    # Init AI
    shared.args.load_in_4bit=True
    shared.args.no_stream=True
    shared.model_name = shared.args.model
    shared.model, shared.tokenizer = load_model(shared.args.model)
    # Connect bot
    token=open('discordtoken.txt').read().strip()
    bot.run(token)

main()
