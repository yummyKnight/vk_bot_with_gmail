import vk_api.vk_api
from vk_api.bot_longpoll import VkBotLongPoll
from vk_api.bot_longpoll import VkBotEventType
from random import randint
import requests
from pprint import pprint
from gmail_reader import GmailAgent
import threading
import logging
import time


class Server:

    def __init__(self, api_token, group_id, server_name: str = "Empty"):
        # Даем серверу имя
        self.server_name = server_name
        # Vk stuff
        self.vk = vk_api.VkApi(token=api_token)
        self.long_poll = VkBotLongPoll(self.vk, group_id)
        self.vk_api = self.vk.get_api()

        self.gmail = GmailAgent()

        self.lock = threading.Lock()
        # logger config
        self.logger = logging.getLogger("vk_bot")
        handler = logging.FileHandler('sample.log', 'a+', 'utf-8')
        formatter = logging.Formatter("%(asctime)s %(name)s:%(levelname)s:%(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    @staticmethod
    def _random_id():
        return randint(-1000000, 1000000)

    def send_msg(self, send_id, message):
        """
        Отправка сообщения через метод messages.send
        :param send_id: vk id пользователя, который получит сообщение
        :param message: содержимое отправляемого письма
        :return: None
        """
        self.vk_api.messages.send(peer_id=send_id,
                                  message=message,
                                  random_id=self._random_id())

    def send_message(self, message, random_id, peer_id=2000000001):
        with self.lock:
            self.vk_api.messages.send(chat_id=116, peer_id=peer_id, message=message,
                                      random_id=random_id)

    def get_members(self, peer_id):
        return self.vk_api.messages.getConversationMembers(chat_id=116, peer_id=peer_id)

    def start(self):
        self.logger.info("Бот начал свою работу!")
        thread1 = threading.Thread(target=Server.massage_replying, args=(self,))
        thread2 = threading.Thread(target=Server.start_monitoring_gmail, args=(self,))
        thread1.start()
        thread2.start()
        thread1.join()

    # TODO: Refractor this function to reduce Cognitive Complexity
    def massage_replying(self):
        try:
            while True:
                for event in self.long_poll.listen():
                    try:
                        if event.type == VkBotEventType.MESSAGE_NEW:
                            text: str = event.message["text"]
                            self.logger.info("Бот ответил на новое письмо из беседы" + str(event))
                            peer_id = event.object["message"]["peer_id"]
                            if text.replace(" ", "").split("!")[-1] == "all":
                                pprint(self.get_members(peer_id))
                            elif text.replace(" ", "").split("!")[-1] == "hi":
                                self.send_message("Buenos dias", self._random_id(), peer_id)
                            elif text.replace(" ", "").split("!")[-1] == "bye":
                                self.send_message("Adios", self._random_id(), peer_id)
                            elif text.replace(" ", "").split("!")[-1] == "debug":
                                self.send_message(
                                    "Вот сырец последнего сообщения:\n" + self.gmail.get_last_message_raw(),
                                    self._random_id(), peer_id)
                            else:
                                self.send_message(
                                    "Неизвестная команда, смертный",
                                    self._random_id(), peer_id)
                    except requests.exceptions.ReadTimeout:
                        continue
                    except requests.exceptions.ConnectionError as e:
                        self.logger.info("Потеря соединения с сервером vk " + str(e))
                        time.sleep(30)

        except Exception as e:
            self.send_message("Случилась страшная и непредвиденная ошибка:\n" + str(
                e) + "Бот завершает свою работу до выяснения причин.", random_id=self._random_id())
            self.logger.critical(e.__str__())
            self.logger.info("Бот окончил свою работу!")
            return -1

    # TODO: Refractor this function to reduce Cognitive Complexity
    def start_monitoring_gmail(self):
        try:
            gmail = self.gmail
            while True:
                if gmail.scan_for_new_message():
                    email_list = gmail.get_info_from_message()
                    for email_dict in email_list:
                        string_list = list()
                        string_list.append("Новое сообщение на почте, смертные.\n От: " + email_dict["From"])
                        string_list.append("Тема: " + email_dict["Subject"])
                        if email_dict["Snippet"]:
                            string_list.append("Snippet: " + email_dict["Snippet"])
                        # need refactoring
                        for part in email_dict["Body"]:
                            for subpart in part:
                                string_list.append(subpart)
                        string_list.append("Дата: " + email_dict["Date"])
                        string_list.append("Количество прикрепленных файлов: " + str(email_dict["Attach_Num"]))
                        self.send_message("\n".join(string_list), self._random_id())
                        self.logger.info("Бот выслал в беседу новое письмо!")
                time.sleep(30)
        except Exception as e:
            self.send_message("Случилась страшная и непредвиденная ошибка:\n" + str(
                e) + "Бот завершает свою работу до выяснения причин.", random_id=self._random_id())
            self.logger.critical(e.__str__())
            self.logger.info("Бот окончил свою работу!")
            return -1


if __name__ == '__main__':
    server1 = Server(api_token, group_id,
                     "server1")
    server1.start()
