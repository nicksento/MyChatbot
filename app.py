"""
Main app file for Research Assistant Chatbot
"""
import os
import chainlit as cl
import google.generativeai as genai
from dotenv import load_dotenv
from utils import (delete_directory,
                   get_documents)

load_dotenv()
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])


@cl.on_chat_start
async def on_chat_start():

    await cl.Message(
        content="Which topic would you like to research?").send()

    documents_retrieved = 0
    cl.user_session.set("documents_retrieved", documents_retrieved)


@cl.on_message
async def main(message: cl.Message):

    documents_retrieved = cl.user_session.get("documents_retrieved")
    if documents_retrieved == 0:
        chat = await get_documents(message.content)
        cl.user_session.set("chat", chat)
        documents_retrieved = 1
        cl.user_session.set("documents_retrieved", documents_retrieved)
        return None

    # Wait fot the user to ask an Arxiv question
    chat = cl.user_session.get("chat")
    response = chat.send_message(message.content)

    await cl.Message(content=response.text).send()

@cl.on_chat_end
async def on_chat_end():
    delete_directory("downloads")
