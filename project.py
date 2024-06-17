import streamlit as st
import json
from openai import OpenAI

def load_data(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("파일을 찾을 수 없습니다.")
        return None
    except json.JSONDecodeError:
        st.error("JSON 파일을 읽는 중 오류가 발생했습니다.")
        return None

data = load_data('book100.json')

if data:
    titles = data.get('title', [])
    introduces = data.get('introduce', [])
    tocs = data.get('toc', [])

    st.title("도서 검색 웹 애플리케이션")
    
    key = search_title = st.text_input("key:")
    client = OpenAI(api_key=key)

    def get_similar_books(input):
        # 파일
        vector_store = client.beta.vector_stores.create(name="BOOK")

        file_streams = []
        for i in range(100):
            file_streams.append(open(f"books/book{i+1}.json", "rb"))

        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=file_streams
        )

        Prompt = "첨부 파일에서 입력 내용과 유사한 책을 찾고, 그 책의 title을 csv형식으로 구분자는 '\\n'으로 하고 출력하세요. \n\n입력: "
        #Prompt = "입력 내용과 유사한 책을 첨부 파일에서 찾아서 title과 전체 내용을 요약해서 출력해 \n출력 예: 제목:title \n -내용:...  \n\n입력: "

        assistant = client.beta.assistants.create(
            instructions= '당신은 사서입니다. 첨부 파일의 정보를 이용해 응답하세요.',
            model="gpt-4o",
            tools=[{"type": "file_search"}],
            tool_resources={
                "file_search":{
                    "vector_store_ids": [vector_store.id]
                }
            }
        )

        #thread
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": Prompt + input,
                }
            ]
        )

        run = client.beta.threads.runs.create_and_poll( # 1초에 1회 호출 (분당 100회 제한)
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        # message
        thread_messages = client.beta.threads.messages.list(thread.id, run_id=run.id)
        recommended_books = thread_messages.data[0].content[0].text.value
        # delete thread
        response = client.beta.threads.delete(thread.id)

        # delete assistant
        response = client.beta.assistants.delete(assistant.id)

        # delete vector store
        response = client.beta.vector_stores.delete(vector_store.id)

        response = client.files.list(purpose="assistants")
        for file in response.data:
            client.files.delete(file.id)
        
        return recommended_books

    @st.cache_data
    def get_summary(toc):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": f"아래의 목차를 요약해줘.\n{toc}"}
            ]
        )

        return response.choices[0].message.content

    st.header("도서 검색")  
    isSummary = st.checkbox("도서 요약(느림)")
    search_title = st.text_input("도서 제목 혹은 도서의 내용을 입력하세요:")

    if st.button("검색하기"):
        with st.spinner('검색 중 ...'):
            book = get_similar_books(search_title)
        books = book.split('\n')

        st.write(f"'{search_title}'에 대한 검색 결과:")
        
        books = list(set(books) & set(titles))
        if books != []:
            for book in books:
                st.write(f"제목: {book}")
                if isSummary == True:
                    st.write('# 내용 요약')
                    index = titles.index(book)
                    with st.spinner('요약 중 ...'):
                        summary = get_summary(tocs[index])
                    st.write(summary)
                
            st.subheader('상세 내용')
            for book in books:
                index = titles.index(book)
                with st.expander(book):
                    st.write("**소개**")
                    st.write(introduces[index] if introduces[index] != '' else "소개 정보가 없습니다.")
                    st.write("**목차**")
                    st.write(tocs[index] if tocs[index] != '' else "목차 정보가 없습니다.")
        else:
            st.write('검색 결과가 없습니다. 다시 검색해주세요.')

        
else:
    st.error("도서 데이터를 불러오는 중 문제가 발생했습니다.")
