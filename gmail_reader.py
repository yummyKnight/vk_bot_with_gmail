import pickle
import os.path
import email
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64
import dateutil.parser as parser
from googleapiclient.errors import HttpError
import html2text
import pprint
from email.header import decode_header
from outside import getmailheader
from numpy.core import unicode

# source 1 https://github.com/abhishekchhibber/Gmail-Api-through-Python/blob/master/gmail_read.py
# source 2 https://gist.github.com/ktmud/cb5e3ca0222f86f5d0575caddbd25c03
# TODO: -- refractor this shit-code
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


class GmailAgent:
    def __init__(self):
        is_token_available = os.path.exists('token.pickle')
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        self.message = None
        self.message_info = dict()
        if is_token_available:
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        self._login_and_save_token(creds)
        self.service = build('gmail', 'v1', credentials=creds)

    # def _find_massage_in_mailbox(self, user_id='me', label_id="UNSEEN"):
    #     """List all Messages of the user's mailbox with label_ids applied.
    #
    #     Args:
    #       service: Authorized Gmail API service instance.
    #       user_id: User's email address. The special value "me"
    #       can be used to indicate the authenticated user.
    #       label_id: Only return Messages with this labelId applied.
    #
    #     Returns:
    #       Message that have all required Labels applied. Note that the
    #       returned list contains Message IDs, you must use get with the
    #       appropriate id to get the details of a Message.
    #     """
    #     service = self.service
    #     try:
    #         response = service.users().messages().list(userId=user_id,
    #                                                    labelIds=[label_id]).execute()
    #         messages = []
    #         if 'messages' in response:
    #             messages.extend(response['messages'])
    #
    #         while 'nextPageToken' in response:
    #             page_token = response['nextPageToken']
    #             response = service.users().messages().list(userId=user_id,
    #                                                        labelIds=[label_id],
    #                                                        pageToken=page_token).execute()
    #             messages.extend(response['messages'])
    #         return messages
    #     except HttpError as e:
    #         print(e.content)

    def get_info_from_message(self):
        #         self.message = None
        #         self.message_info = dict()
        for message_id in ListMessagesWithLabels(self.service, 'me', ["INBOX"]):
            self.message = GetMimeMessage(self.service, 'me', message_id["id"])
            self._parse_header()
            self._parse_body()
            self._get_message_snippet()
            pprint.pprint(self.message_info)

    def _parse_body(self):
        # Get the messages
        # charset = msg.get_param('charset', 'utf-8').lower()
        # update charset aliases
        # charset = email.charset.ALIASES.get(charset, charset)
        # msg.set_param('charset', charset)
        body = self.message_info["Body"] = list()
        msg = self.message
        if msg.is_multipart():
            main_content = None
            # multi-part emails often have both
            # a text/plain and a text/html part.
            # Use the first `text/plain` part if there is one,
            # otherwise take the first `text/*` part.
            for part in msg.get_payload():
                is_txt = part.get_content_type() == 'text/plain'
                if not main_content or is_txt:
                    main_content = extract_body(part)
                if is_txt:
                    break
            if main_content:
                body.extend(main_content)
        elif msg.get_content_type().startswith("text/"):
            if self.message.get_content_type() == "text/plain":
                body.append(self._handle_plain_text())
            elif self.message.get_content_type() == "text/html":
                body.append(self._handle_html_text())
            else:
                raise TypeError("Unsupportable type")

    def _handle_plain_text(self):
        body = list()
        msg = self.message
        # msg.get_params() - return 2 tuples. Second element in second tuple stores letter encoding.
        encoding = msg.get_params()[1][1]
        if encoding == 'flowed':
            clean_two = msg.get_payload()
        else:
            base64_info = msg.get_payload(decode=True)
            clean_two = base64_info.decode(encoding)
        body.append(clean_two)
        return body
        # TODO: add exception handler

    def _handle_html_text(self):
        body = list()
        msg = self.message
        base64_info = msg.get_payload()
        text = html2text.html2text(base64_info)
        body.append(text)
        return body

    def _parse_header(self):
        self.message_info["Subject"] = self._parse_parameter_from_header(self.message.get('Subject',' '))
        self.message_info["From"] = self._parse_parameter_from_header(self.message.get('From'))
        self.message_info["To"] = self._parse_parameter_from_header(self.message.get('To'))
        self.message_info["Date"] = self._parse_date_from_header()

    def _parse_parameter_from_header(self, parameter):
        default_encoding = "utf-8"
        try:
            headers = decode_header(parameter)
        except email.errors.HeaderParseError:
            # This already appended in email.base64mime.decode()
            # instead return a sanitized ascii string
            return parameter.encode('ascii', 'replace').decode('ascii')
        else:
            for k, (text, charset) in enumerate(headers):
                try:
                    headers[k] = unicode(text, charset or default_encoding, errors='replace')
                except LookupError:
                    # if the charset is unknown, force default
                    headers[k] = unicode(text, default_encoding, errors='replace')
                except TypeError:
                    headers[k] = text
            return u"".join(headers)

    def _parse_date_from_header(self):
        date = parser.parse(self.message.get('Received').split(";")[1].strip()).date().strftime("%d/%m/%Y")
        return date

    def _get_message_snippet(self):
        self.message_info['Snippet'] = self.message['snippet']

    def _login_and_save_token(self, creds):
        # !!!important creds will be modified
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        return creds


def GetMimeMessage(service, user_id, msg_id):
    """Get a Message and use it to create a MIME Message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The ID of the Message required.

    Returns:
      A MIME Message, consisting of data from Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id,
                                                 format='raw').execute()

        # print('Message snippet: %s' % message['snippet'])
        msg_str = base64.urlsafe_b64decode(message['raw'].encode('utf-8'))
        mime_msg = email.message_from_string(msg_str.decode("utf-8", errors='replace'))

        return mime_msg
    except HttpError as error:
        print(f'An error occurred: {error}')


def GetMessage(service, user_id, msg_id):
    """Get a Message with given ID.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      msg_id: The ID of the Message required.

    Returns:
      A Message.
    """
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()

        # print('Message snippet: %s' % message['snippet'])

        return message
    except HttpError as error:
        print(f'An error occurred: {error}')


def ListMessagesWithLabels(service, user_id, label_ids=[]):
    """List all Messages of the user's mailbox with label_ids applied.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      label_ids: Only return Messages with these labelIds applied.

    Returns:
      List of Messages that have all required Labels applied. Note that the
      returned list contains Message IDs, you must use get with the
      appropriate id to get the details of a Message.
    """
    try:
        response = service.users().messages().list(userId=user_id,
                                                   labelIds=label_ids).execute()
        messages = []
        if 'messages' in response:
            messages.extend(response['messages'])

        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId=user_id,
                                                       labelIds=label_ids,
                                                       pageToken=page_token).execute()
            # messages.extend(response['messages'])
        return messages
    except HttpError as e:
        print(e.content)


def extract_body(msg, depth=0):
    """ Extract content body of an email messsage """
    body = []
    if msg.is_multipart():
        main_content = None
        # multi-part emails often have both
        # a text/plain and a text/html part.
        # Use the first `text/plain` part if there is one,
        # otherwise take the first `text/*` part.
        for part in msg.get_payload():
            is_txt = part.get_content_type() == 'text/plain'
            if not main_content or is_txt:
                main_content = extract_body(part)
            if is_txt:
                break
        if main_content:
            body.extend(main_content)
    elif msg.get_content_type().startswith("text/"):
        # Get the messages
        # charset = msg.get_param('charset', 'utf-8').lower()
        # update charset aliases
        # charset = email.charset.ALIASES.get(charset, charset)
        # msg.set_param('charset', charset)

        if msg.get_content_type() == "text/plain":
            try:

                # clean_one = base64_info.replace("-", "+")  # decoding from Base64 to UTF-8
                # clean_one = clean_one.replace("_", "/")  # decoding from Base64 to UTF-8
                # print("original : ", clean_one)
                code = msg.get_params()[1][1]
                if code == 'flowed':
                    clean_two = msg.get_payload()
                else:
                    base64_info = msg.get_payload(decode=True)
                    clean_two = base64_info.decode(code)
                # if msg["Content-Transfer-Encoding"] == "base64":
                #     clean_two = base64.urlsafe_b64decode(clean_one).decode(code)  # decoding from Base64 to UTF-8
                # else:
                print(f"\n8////////////////\n{code}\n////////////////8\n")
                #     clean_two = quopri.decodestring(clean_one).decode(code)
                body.append(clean_two)
            except AssertionError as e:
                print('Parsing failed.    ')
                print(e)
            except LookupError:
                # set all unknown encoding to utf-8
                # then add a header to indicate this might be a spam
                msg.set_param('charset', 'utf-8')
                body.append('=== <UNKOWN ENCODING POSSIBLY SPAM> ===')
                body.append(msg.get_content())
            except AttributeError:
                print(msg)
        elif msg.get_content_type() == "text/html":
            base64_info = msg.get_payload()
            text = html2text.html2text(base64_info)
            body.append(text)
            # body.append(base64_info)
        else:
            raise TypeError("Unsupportable type")
    return body


def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
    else:
        print('Labels:')
        for label in labels:
            print(label['name'])
    for message_id in ListMessagesWithLabels(service, 'me', ["INBOX"]):
        answer = GetMimeMessage(service, 'me', message_id["id"])
        print("------------/-/-/------------------------//-------------------/-/-/")
        t = extract_body(answer)
        print(t)
        print(t[0])
        print("------------/-/-/------------------------//-------------------/-/-/")


if __name__ == '__main__':
    GmailAgent().get_info_from_message()
