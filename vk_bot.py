import vk_api.vk_api
from vk_api.bot_longpoll import VkBotLongPoll
from vk_api.bot_longpoll import VkBotEventType
from random import randint
import requests
from pprint import pprint
from gmail_reader import GmailAgent
import threading
import CREDS


class Server:

    def __init__(self, api_token, group_id, server_name: str = "Empty"):
        # Даем серверу имя
        self.server_name = server_name

        # Для Long Poll
        self.vk = vk_api.VkApi(token=api_token)

        # Для использования Long Poll API
        self.long_poll = VkBotLongPoll(self.vk, group_id)
        self.gmail = GmailAgent()
        # Для вызова методов vk_api
        self.vk_api = self.vk.get_api()

        self.lock = threading.Lock()

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

    def test(self):
        # Посылаем сообщение пользователю с указанным ID
        self.send_msg(27209699, "Чмо")

    def send_message(self, message, random_id, peer_id=2000000001):
        with self.lock:
            self.vk_api.messages.send(chat_id=116, peer_id=peer_id, message=message,
                                      random_id=random_id)

    def get_members(self, peer_id):
        return self.vk_api.messages.getConversationMembers(chat_id=116, peer_id=peer_id)

    def massage_replying(self):
        while True:
            for event in self.long_poll.listen():
                pprint(event)
                try:
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        pprint(event)
                        text: str = event.message["text"]
                        peer_id = event.object["message"]["peer_id"]
                        if text.replace(" ", "") == "[club192941765|Grumpybot]!all":
                            pprint(self.get_members(peer_id))
                        if text.replace(" ", "") == "[club192941765|Grumpybot]!hi":
                            self.send_message("Buenos dias, pedrilas", self._random_id(), peer_id)
                        if text.replace(" ", "") == "[club192941765|Grumpybot]!bye":
                            self.send_message("Adios, pedrilas", self._random_id(), peer_id)
                        if text.replace(" ", "") == "[club192941765|Grumpybot]!debug":
                            self.send_message(
                                "Вот сырец последнего сообщения:\n" + self.gmail.get_last_message_raw(),
                                self._random_id(), peer_id)
                except requests.exceptions.ReadTimeout:
                    continue

    def start(self):
        try:
            thread1 = threading.Thread(target=Server.massage_replying, args=(self,))
            thread2 = threading.Thread(target=Server.start_monitoring_gmail, args=(self,))
            thread1.start()
            thread2.start()
            thread1.join()
        except Exception as e:
            self.send_message("Случилась страшная и непредвиденная ошибка:\n" + str(
                e) + "Бот завершает свою работу до выяснения причин.", random_id=self._random_id())
            return -1

    def start_monitoring_gmail(self):
        gmail = self.gmail
        while True:
            if gmail.scan_for_new_message():
                email_list = gmail.get_info_from_message()
                for email_dict in email_list:
                    string_list = list()
                    string_list.append("Новое сообщение на почте, смертные.\n От: " + email_dict["From"])
                    string_list.append("Для: " + email_dict["To"])
                    string_list.append("Тема: " + email_dict["Subject"])
                    if email_dict["Snippet"]:
                        string_list.append("Snippet: " + email_dict["Snippet"])
                    for part in email_dict["Body"]:
                        for subpart in part:
                            string_list.append(subpart)
                    string_list.append("Дата: " + email_dict["Date"])
                    string_list.append("Количество прикрепленных файлов: " + str(email_dict["Attach_Num"]))
                    self.send_message("\n".join(string_list), self._random_id())


if __name__ == '__main__':
    server1 = Server(CREDS.Creds.api_token, CREDS.Creds.group_id,
                     "server1")
    # vk_api_token - API токен, который мы ранее создали
    # 172998024 - id сообщества-бота
    # "server1" - имя сервера
    server1.start()
