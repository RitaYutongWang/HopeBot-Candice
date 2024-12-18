import streamlit as st
from streamlit_chat import message
import os
import time
from audio_recorder_streamlit import audio_recorder
from streamlit_float import float_init
import base64

# --------------------------------------------------------------------------------------------------------------------------logic2END
import openai
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
import streamlit as st
import openai
from langchain_community.chat_models import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain
from langchain_core.runnables import RunnablePassthrough
from langchain_community.document_loaders import TextLoader
import chardet
import pysqlite3 as sqlite3
import sys

st.set_page_config(page_title="HopeBot: Your Mental Health Assistant", layout="wide")
sys.modules["sqlite3"] = sqlite3
load_dotenv()
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Function to initialize resources
@st.cache_resource
def initialize_resources():
    # Chat model
    chat = ChatOpenAI(
        model="gpt-4o",
        temperature=0.4,
    )

    # Detect file encoding
    with open(r'cleaned_data.txt', 'rb') as f:
        result = chardet.detect(f.read())
        encoding = result['encoding']

    # Embedding model
    embed_model = OpenAIEmbeddings()

    # Vector stores
    vectorstore1 = Chroma(
        embedding_function=embed_model, 
        persist_directory="cleaned_data"
    )
    vectorstore2 = Chroma(
        embedding_function=embed_model, 
        persist_directory="mental_health"
    )
    vectorstore3 = Chroma(
        embedding_function=embed_model, 
        persist_directory="econ"
    )

    # Retrievers
    retriever1 = vectorstore1.as_retriever(k=2)
    retriever2 = vectorstore2.as_retriever(k=2)
    retriever3 = vectorstore3.as_retriever(k=2)

    # ChatPromptTemplate
    question_answering_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", """
             You are HopeBot, a professional psychotherapist specialising in Cognitive Behavioural Therapy (CBT). Your role is to focus on your clients' words and emotions, guiding them to reflect on their thoughts and behaviours through open-ended questions and guiding them through the PHQ-9 test. Always show empathy and understanding of their feelings and help them to recognise how their behaviour affects their emotions.Your responses should not be too long or presented in bullet point form, which is too mechanical, and all your responses should be spoken. If a customer comes to you for advice, give two or three at a time.
    You need to complete three tasks in turn:
    Task 1: As a professional counsellor, you should begin by greeting the client warmly and start a casual conversation asking about their current situation. Do not exceed 20 rounds of dialogue in this task and transition to introducing the PHQ-9 when appropriate, if the user states twice or more that they have nothing to share or when the dialogue up to 20 rounds, you must ask the user if they would like to take the PHQ-9 test and give a brief introduction to the PHQ-9, communicating that this can be seen as a tool to help understand their feelings and offer support.
    
    Task 2: After the user agrees to use the PHQ-9, ask each question in turn. Accurately categorise the user's answers as options A, B, C or D. If the user's answer is not precise enough, ambiguous or cannot be accurately categorised, ask the user to provide a clearer answer to ensure that the most accurate answer is collected. If the user answers A, they get 0 points; B, 1 point; C, 2 points; and D, 3 points. Track the score cumulatively without displaying it, and move to Task 3 after completing the test.
    
    Task 3: You must first tell the user of their answer distribution. In the format: Here’s how each answer was interpreted: Question 1: X (X point), etc. Then sum each question's mark up, and tell the user of their total score in number on the PHQ-9. In the format: You scored X points. And provide the appropriate depression severity results. Provide appropriate advice based on the results. If the depression is severe, give your advice and also encourage the user to seek professional help and provide them with a UK telephone helpline or email address (no more than 2 contacts). Be sure to make it clear that you are a virtual mental health assistant, not a doctor, and that whilst you will offer help, you are not a substitute for professional medical advice.
    At the end you will need to provide a brief summary of your conversation, including the confusion raised by the user in Task 1, as well as their PHQ-9 test results, and your corresponding recommendations. You need to ask the user if they have any further questions about the result and answer them.
    
    Please maintain the demeanour of a professional psychologist at all times and show empathy in your interactions. Please keep your responses concise and avoid giving long, repetitive answers.
    Here is some additional background information to help guide your responses:\n\n{context}
            """),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    # Create the LLM chain with the language model and the prompt
    document_chain = LLMChain(llm=chat, prompt=question_answering_prompt)

    # Return all initialized resources
    return chat, retriever1, retriever2, retriever3, question_answering_prompt, document_chain

# Initialize resources (runs once and caches results)
chat, retriever1, retriever2, retriever3, question_answering_prompt, document_chain = initialize_resources()

# Function to process input and return the chatbot's response
def get_assistant_response(messages):
    # Extract the user's last message (the latest user input)
    user_input = messages[-1]["content"]

    # Simulate chat history
    chat_history = ChatMessageHistory()
    for message in messages:
        chat_history.add_message(HumanMessage(content=message["content"]) if message["role"] == "user" else AIMessage(content=message["content"]))

    # Retrieve documents based on user input
    retriever_context = user_input  # Use user input as the query for document retrieval
    retrieved_docs1 = retriever1.get_relevant_documents(retriever_context)
    retrieved_docs2 = retriever2.get_relevant_documents(retriever_context)
    retrieved_docs3 = retriever3.get_relevant_documents(retriever_context)

    # Combine retrieved content into one context
    combined_context = "\n".join([doc.page_content for doc in retrieved_docs1 + retrieved_docs2 + retrieved_docs3])

    # Generate chatbot response with retrieved context
    response = document_chain.run(
        {
            "context": combined_context,  # Documents retrieved from retrievers
            "messages": chat_history.messages  # Conversation history
        }
    )

    # Return the assistant's response
    return response


def speech_to_text(audio_data):
    with open(audio_data, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1",
            response_format="text",
            file=audio_file
        )
    return transcript

def text_to_speech(input_text):
    response = openai.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=input_text
    )
    webm_file_path = "temp_audio_play.mp3"
    with open(webm_file_path, "wb") as f:
        response.stream_to_file(webm_file_path)
    return webm_file_path

def autoplay_audio(file_path: str):
    with open(file_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("utf-8")
    md = f"""
    <audio autoplay>
    <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
    </audio>
    """
    st.markdown(md, unsafe_allow_html=True)
# ------------------------------------------------------------------------------------------------------------------------------------------------logic2END

# Float feature initialization
float_init()

# 初始化会话状态
def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "This is HopeBot, your mental health assistant. It's good to hear from you, how are you doing today? 😊"}
        ]

initialize_session_state()

# 标题
st.title("HopeBot: Your Mental Health Assistant 🤖")

# 语音识别功能
def speech_to_text(audio_path):
    with open(audio_path, "rb") as audio_file:
        transcript = openai.audio.transcriptions.create(
            model="whisper-1", response_format="text", file=audio_file
        )
    return transcript.strip()

# 语音合成功能
def text_to_speech(text):
    response = openai.audio.speech.create(model="tts-1", voice="nova", input=text)
    audio_path = "response_audio.mp3"
    with open(audio_path, "wb") as f:
        response.stream_to_file(audio_path)
    return audio_path

# 音频播放功能
def autoplay_audio(file_path):
    with open(file_path, "rb") as f:
        data = f.read()
    b64_audio = base64.b64encode(data).decode("utf-8")
    st.markdown(
        f"""
        <audio autoplay>
        <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

# 浮动容器（用于麦克风）
float_init()
footer_container = st.container()
with footer_container:
    audio_bytes = audio_recorder(energy_threshold=(-1, 0.5), pause_threshold=5.0, sample_rate=16000)

# 显示聊天历史（使用气泡样式和头像）
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else "👤"):
        st.markdown(
            f"<p style='font-size: 24px; margin: 0;'>{message['content']}</p>",
            unsafe_allow_html=True
        )

# 处理语音输入
if audio_bytes:
    with st.spinner("Transcribing..."):
        audio_path = "temp_audio.mp3"
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        transcript = speech_to_text(audio_path)
        if transcript:
            # 添加用户消息
            st.session_state.messages.append({"role": "user", "content": transcript})
            with st.chat_message("user", avatar="👤"):
                st.markdown(
                    f"<p style='font-size: 24px; margin: 0;'>{transcript}</p>",
                    unsafe_allow_html=True
                )
            os.remove(audio_path)

# 生成 HopeBot 回复
if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking🤔..."):
            final_response = get_assistant_response(st.session_state.messages)  # Passing session messages to the function
            st.markdown(
                f"<p style='font-size: 24px; margin: 0;'>{final_response}</p>",
                unsafe_allow_html=True
            )
        with st.spinner("HopeBot is speaking💬..."):    
            audio_file = text_to_speech(final_response)
            autoplay_audio(audio_file)
        st.session_state.messages.append({"role": "assistant", "content": final_response})
        os.remove(audio_file)

# 浮动的麦克风按钮
footer_container.float("bottom: 0rem;")
