FROM python:3.11-alpine

RUN pip install python-dotenv pyTelegramBotAPI pandas openpyxl openai

COPY . .

CMD ["python", "main.py"]