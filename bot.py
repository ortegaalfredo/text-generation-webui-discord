import discord
import os
import sys
import time
import json
import threading
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
class Msg:
    message: discord.Message
    reply: str

msgqueue=[]

def thread_generate():
    while(True):
        time.sleep(1)
        if len(msgqueue)>0:
            msg=msgqueue[0]
            if (len(msg.reply)==0):
                msg.reply=answerMessage(msg.message)


@tasks.loop(seconds=1)
async def thread_reply():
        global msgqueue
        if len(msgqueue)>0:
            reply=msgqueue[0].reply
            message=msgqueue[0].message
            # write 'typing' in every channel
            for m in msgqueue:
                await m.message.channel.typing()
            if (len(reply)>0):
                print ('reply received')
                msg=msgqueue.pop(0)
                await bot.change_presence(activity=discord.Game(name='Queue: %d'% len(msgqueue)))
                #send reply
                if len(reply)>1500:
                    for i in range(0,len(reply),1500):
                        await message.channel.send(reply[i:i+1500], reference=message)
                else:
                    await message.channel.send(reply,reference=message)

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
    print ('message received: %s %s' % (botid,message.content))
    if message.content.startswith(botid):
        print ('message accepted.')
        newMsg = Msg()
        newMsg.message=message
        newMsg.reply=""
        msgqueue.append(newMsg)
        

def answerMessage(message):
        # Default config values
        temperature= 1.5
        top_p= 0.1
        top_k=40
        max_len=192
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
                        if (max_len>400): max_len=400
                    if not (config.get('repetition_penalty') is None):
                        repetition_penalty=float(config['repetition_penalty'])
        except Exception as e:
                msg = f"{message.author.mention} Error parsing the Json config: %s" % str(e)
                log(msg)
                return(msg)
                return

        if (query.startswith('raw ')): # Raw prompt
                query = query[4:]
        else: # Wrap prompt in question
                query =query #'The answer for "%s" would be: ' % query
        print(origquery)
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
                return(msg)
        log("---"+str(origquery))
        
        for result in results:
            msg = f"{message.author.mention} {result[0]}"
            log(msg)
            return msg
            break

def main():
    # Init AI
    shared.args.load_in_4bit=True
    shared.args.no_stream=True
    shared.model_name = shared.args.model
    shared.model, shared.tokenizer = load_model(shared.args.model)
    # Starting reply thread
    print('Starting reply thread')
    x = threading.Thread(target=thread_generate,args=())
    x.start()
    # Connect bot
    token=open('discordtoken.txt').read().strip()
    bot.run(token)

main()
