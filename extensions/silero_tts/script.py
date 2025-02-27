import re
import time
from pathlib import Path

import gradio as gr
import torch

import modules.chat as chat
import modules.shared as shared

torch._C._jit_set_profiling_mode(False)

params = {
    'activate': True,
    'speaker': 'en_5',
    'language': 'en',
    'model_id': 'v3_en',
    'sample_rate': 48000,
    'device': 'cpu',
    'show_text': False,
    'autoplay': True,
    'voice_pitch': 'medium',
    'voice_speed': 'medium',
}

current_params = params.copy()
voices_by_gender = ['en_99', 'en_45', 'en_18', 'en_117', 'en_49', 'en_51', 'en_68', 'en_0', 'en_26', 'en_56', 'en_74', 'en_5', 'en_38', 'en_53', 'en_21', 'en_37', 'en_107', 'en_10', 'en_82', 'en_16', 'en_41', 'en_12', 'en_67', 'en_61', 'en_14', 'en_11', 'en_39', 'en_52', 'en_24', 'en_97', 'en_28', 'en_72', 'en_94', 'en_36', 'en_4', 'en_43', 'en_88', 'en_25', 'en_65', 'en_6', 'en_44', 'en_75', 'en_91', 'en_60', 'en_109', 'en_85', 'en_101', 'en_108', 'en_50', 'en_96', 'en_64', 'en_92', 'en_76', 'en_33', 'en_116', 'en_48', 'en_98', 'en_86', 'en_62', 'en_54', 'en_95', 'en_55', 'en_111', 'en_3', 'en_83', 'en_8', 'en_47', 'en_59', 'en_1', 'en_2', 'en_7', 'en_9', 'en_13', 'en_15', 'en_17', 'en_19', 'en_20', 'en_22', 'en_23', 'en_27', 'en_29', 'en_30', 'en_31', 'en_32', 'en_34', 'en_35', 'en_40', 'en_42', 'en_46', 'en_57', 'en_58', 'en_63', 'en_66', 'en_69', 'en_70', 'en_71', 'en_73', 'en_77', 'en_78', 'en_79', 'en_80', 'en_81', 'en_84', 'en_87', 'en_89', 'en_90', 'en_93', 'en_100', 'en_102', 'en_103', 'en_104', 'en_105', 'en_106', 'en_110', 'en_112', 'en_113', 'en_114', 'en_115']
voice_pitches = ['x-low', 'low', 'medium', 'high', 'x-high']
voice_speeds = ['x-slow', 'slow', 'medium', 'fast', 'x-fast']
last_msg_id = 0

# Used for making text xml compatible, needed for voice pitch and speed control
table = str.maketrans({
    "<": "&lt;",
    ">": "&gt;",
    "&": "&amp;",
    "'": "&apos;",
    '"': "&quot;",
})

def xmlesc(txt):
    return txt.translate(table)

def load_model():
    model, example_text = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts', language=params['language'], speaker=params['model_id'])
    model.to(params['device'])
    return model
model = load_model()

def remove_surrounded_chars(string):
    new_string = ""
    in_star = False
    for char in string:
        if char == '*':
            in_star = not in_star
        elif not in_star:
            new_string += char
    return new_string

def remove_tts_from_history():
    suffix = '_pygmalion' if 'pygmalion' in shared.model_name.lower() else ''
    for i, entry in enumerate(shared.history['internal']):
        reply = entry[1]
        reply = re.sub("(<USER>|<user>|{{user}})", shared.settings[f'name1{suffix}'], reply)
        if shared.args.chat:
            reply = reply.replace('\n', '<br>')
        shared.history['visible'][i][1] = reply

    if shared.args.cai_chat:
        return chat.generate_chat_html(shared.history['visible'], shared.settings[f'name1{suffix}'], shared.settings[f'name1{suffix}'], shared.character)
    else:
        return shared.history['visible']

def toggle_text_in_history():
    suffix = '_pygmalion' if 'pygmalion' in shared.model_name.lower() else ''
    audio_str='\n\n' # The '\n\n' used after </audio>
    if shared.args.chat:
         audio_str='<br><br>'

    if params['show_text']==True:
        #for i, entry in enumerate(shared.history['internal']):
        for i, entry in enumerate(shared.history['visible']):
            vis_reply = entry[1]
            if vis_reply.startswith('<audio'):
                reply = shared.history['internal'][i][1]
                reply = re.sub("(<USER>|<user>|{{user}})", shared.settings[f'name1{suffix}'], reply)
                if shared.args.chat:
                    reply = reply.replace('\n', '<br>')
                shared.history['visible'][i][1] = vis_reply.split(audio_str,1)[0]+audio_str+reply
    else:
        for i, entry in enumerate(shared.history['visible']):
            vis_reply = entry[1]
            if vis_reply.startswith('<audio'):
                shared.history['visible'][i][1] = vis_reply.split(audio_str,1)[0]+audio_str

    if shared.args.cai_chat:
        return chat.generate_chat_html(shared.history['visible'], shared.settings[f'name1{suffix}'], shared.settings[f'name1{suffix}'], shared.character)
    else:
        return shared.history['visible']

def input_modifier(string):
    """
    This function is applied to your text inputs before
    they are fed into the model.
    """

    # Remove autoplay from previous chat history
    if (shared.args.chat or shared.args.cai_chat)and len(shared.history['internal'])>0:
        [visible_text, visible_reply] = shared.history['visible'][-1]
        vis_rep_clean = visible_reply.replace('controls autoplay>','controls>')
        shared.history['visible'][-1] = [visible_text, vis_rep_clean]

    return string

def output_modifier(string):
    """
    This function is applied to the model outputs.
    """

    global model, current_params

    for i in params:
        if params[i] != current_params[i]:
            model = load_model()
            current_params = params.copy()
            break

    if params['activate'] == False:
        return string

    orig_string = string
    string = remove_surrounded_chars(string)
    string = string.replace('"', '')
    string = string.replace('“', '')
    string = string.replace('\n', ' ')
    string = string.strip()

    silent_string = False # Used to prevent unnecessary audio file generation
    if string == '':
        string = 'empty reply, try regenerating'
        silent_string = True

    pitch = params['voice_pitch']
    speed = params['voice_speed']
    prosody=f'<prosody rate="{speed}" pitch="{pitch}">'
    string = '<speak>'+prosody+xmlesc(string)+'</prosody></speak>'

    if not shared.still_streaming and not silent_string:
        output_file = Path(f'extensions/silero_tts/outputs/{shared.character}_{int(time.time())}.wav')
        model.save_wav(ssml_text=string, speaker=params['speaker'], sample_rate=int(params['sample_rate']), audio_path=str(output_file))
        autoplay_str = ' autoplay' if params['autoplay'] else ''
        string = f'<audio src="file/{output_file.as_posix()}" controls{autoplay_str}></audio>\n\n'
    else:
        # Placeholder so text doesn't shift around so much
        string = '<audio controls></audio>\n\n'

    if params['show_text']:
        string += orig_string

    return string

def bot_prefix_modifier(string):
    """
    This function is only applied in chat mode. It modifies
    the prefix text for the Bot and can be used to bias its
    behavior.
    """

    return string

def ui():
    # Gradio elements
    with gr.Accordion("Silero TTS"):
        with gr.Row():
            activate = gr.Checkbox(value=params['activate'], label='Activate TTS')
            autoplay = gr.Checkbox(value=params['autoplay'], label='Play TTS automatically')
        show_text = gr.Checkbox(value=params['show_text'], label='Show message text under audio player')
        voice = gr.Dropdown(value=params['speaker'], choices=voices_by_gender, label='TTS voice')
        with gr.Row():
            v_pitch = gr.Dropdown(value=params['voice_pitch'], choices=voice_pitches, label='Voice pitch')
            v_speed = gr.Dropdown(value=params['voice_speed'], choices=voice_speeds, label='Voice speed')
        with gr.Row():
            convert = gr.Button('Permanently replace chat history audio with message text')
            convert_confirm = gr.Button('Confirm (cannot be undone)', variant="stop", visible=False)
            convert_cancel = gr.Button('Cancel', visible=False)

    # Convert history with confirmation
    convert_arr = [convert_confirm, convert, convert_cancel]
    convert.click(lambda :[gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, convert_arr)
    convert_confirm.click(lambda :[gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr)
    convert_confirm.click(remove_tts_from_history, [], shared.gradio['display'])
    convert_confirm.click(lambda : chat.save_history(timestamp=False), [], [], show_progress=False)
    convert_cancel.click(lambda :[gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, convert_arr)

    # Toggle message text in history
    show_text.change(lambda x: params.update({"show_text": x}), show_text, None)
    show_text.change(toggle_text_in_history, [], shared.gradio['display'])
    show_text.change(lambda : chat.save_history(timestamp=False), [], [], show_progress=False)

    # Event functions to update the parameters in the backend
    activate.change(lambda x: params.update({"activate": x}), activate, None)
    autoplay.change(lambda x: params.update({"autoplay": x}), autoplay, None)
    voice.change(lambda x: params.update({"speaker": x}), voice, None)
    v_pitch.change(lambda x: params.update({"voice_pitch": x}), v_pitch, None)
    v_speed.change(lambda x: params.update({"voice_speed": x}), v_speed, None)
