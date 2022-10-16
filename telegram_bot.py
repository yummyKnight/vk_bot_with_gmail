import json
import logging
import threading
import time
from typing import Tuple
from gmail_reader import GmailAgent
from telegram.ext import Updater

# def start(update: Update, context: CallbackContext):
#     context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

# def start1(update: Update, context: CallbackContext):
#     context.bot.send_message(chat_id=update.effective_chat.id, text="Сосите!")

def main():
    ts = TelegramServer()
    ts.start()

class TelegramServer:

    def __init__(self, server_name: str = "Empty"):
        self.server_name = server_name
        self.gmail = GmailAgent()
        token, self.group_id = self._read_tg_creds()
        self.updater = Updater(token=token, use_context=True)
        self.bot = self.updater.bot
        self.lock = threading.Lock()
        self.logger = logging.getLogger("vk_bot")
        handler = logging.FileHandler('sample.log', 'a+', 'utf-8')
        formatter = logging.Formatter("%(asctime)s %(name)s:%(levelname)s:%(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _read_tg_creds(self, path : str) -> Tuple[str, str]:
        with open(path, 'r') as f:
            d = json.load(path)
        return d["token"], d["group_id"]
        
    def send_message(self, message):
        with self.lock:
             self.bot.send_message(self.group_id, message)

    def start(self):
        self.logger.info("Бот начал свою работу!")
        # thread1 = threading.Thread(target=Server.massage_replying, args=(self,))
        thread2 = threading.Thread(target=TelegramServer.start_monitoring_gmail, args=(self,))
        thread2.start()

    # TODO: Refractor this function to reduce Cognitive Complexity
    def start_monitoring_gmail(self):
        try:
            gmail = self.gmail
            while True:
                if gmail.scan_for_new_message():
                    email_list = gmail.get_info_from_message()
                    print(email_list)
                    for email_dict in email_list:
                        string_list = list()
                        string_list.append("Новое сообщение на почте.\n От: " + email_dict["From"])
                        string_list.append("Тема: " + email_dict["Subject"])
                        if email_dict["Snippet"]:
                            string_list.append("Snippet: " + email_dict["Snippet"])
                        # need refactoring
                        for part in email_dict["Body"]:
                            for subpart in part:
                                string_list.append(subpart)
                        string_list.append("Дата: " + email_dict["Date"])
                        string_list.append("Количество прикрепленных файлов: " + str(email_dict["Attach_Num"]))
                        self.send_message("\n".join(string_list))
                        self.logger.info("Бот выслал в беседу новое письмо!")
                time.sleep(30)
        except Exception as e:
            self.send_message("Случилась страшная и непредвиденная ошибка:\n" + str(
                e) + "Бот завершает свою работу до выяснения причин.")
            self.logger.critical(e.__str__())
            self.logger.info("Бот окончил свою работу!")
            return -1


if __name__ == "__main__":
    main()