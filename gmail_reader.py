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
from numpy.core import unicode

# source 1 https://github.com/abhishekchhibber/Gmail-Api-through-Python/blob/master/gmail_read.py
# source 2 https://gist.github.com/ktmud/cb5e3ca0222f86f5d0575caddbd25c03
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


class GmailAgent:
    def __init__(self):
        is_token_available = os.path.exists('token.pickle')
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        self._message = None
        self._message_info = dict()
        # TODO: print Attachment's names
        creds = None
        if is_token_available:
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        self._login_and_save_token(creds)
        self._service = build('gmail', 'v1', credentials=creds)

    def get_last_message_text(self):
        return self._message_info.copy()

    def get_last_message_raw(self):
        return self._message.as_string()

    def get_info_from_message(self):
        #         self.message = None
        #         self.message_info = dict()
        result = list()
        for message_id in self._list_messages_with_labels(["UNREAD"]):
            self._message_info["Attach_Num"] = 0
            self._message = self._get_mime_message(message_id["id"])
            self._parse_header()
            self._parse_body(self._message)
            self._get_message_snippet()
            result.append(self._message_info)
            self._service.users().messages().modify(userId='me', id=message_id["id"],
                                                    body={'removeLabelIds': ['UNREAD']}).execute()
        return result

    def scan_for_new_message(self):
        if len(self._list_messages_with_labels(["UNREAD"])) != 0:
            return True
        else:
            return False

    def _list_messages_with_labels(self, label_ids, user_id="me"):
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
            response = self._service.users().messages().list(userId=user_id,
                                                             labelIds=label_ids).execute()
            messages = []
            if 'messages' in response:
                messages.extend(response['messages'])

            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = self._service.users().messages().list(userId=user_id,
                                                                 labelIds=label_ids,
                                                                 pageToken=page_token).execute()
                messages.extend(response['messages'])
            return messages
        except HttpError as e:
            print(e.content)

    def _parse_body(self, msg):
        self._message_info["Body"] = list()
        if msg.is_multipart():
            self._parse_body_part(msg)
        elif msg.get_content_type().startswith("text/"):
            self._parse_text_content(msg)
        return self._message_info["Body"]  # ugly

    def _handle_plain_text(self, msg):
        body = self._message_info["Body"]
        # msg.get_params() - return 2 tuples. Second element in second tuple stores letter encoding.
        encoding = msg.get_params()[1][1]
        if encoding == 'flowed':
            clean_two = msg.get_payload()
        else:
            base64_info = msg.get_payload(decode=True)
            clean_two = base64_info.decode(encoding)
        body.append([clean_two])
        # TODO: add exception handler

    def _get_mime_message(self, msg_id, user_id="me"):
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
            message = self._service.users().messages().get(userId=user_id, id=msg_id,
                                                           format='raw').execute()

            # print('Message snippet: %s' % message['snippet'])
            msg_str = base64.urlsafe_b64decode(message['raw'].encode('utf-8'))
            mime_msg = email.message_from_string(msg_str.decode("utf-8", errors='replace'))

            return mime_msg
        except HttpError as error:
            print(f'An error occurred: {error}')

    def _handle_html_text(self, msg):
        body = self._message_info["Body"]
        base64_info = msg.get_payload()
        text = html2text.html2text(base64_info)
        body.append([text])

    def _parse_header(self):
        self._message_info["Subject"] = self._parse_parameter_from_header(self._message.get('Subject', ' '))
        self._message_info["From"] = self._parse_parameter_from_header(self._message.get('From'))
        self._message_info["To"] = self._parse_parameter_from_header(self._message.get('To'))
        self._message_info["Date"] = self._parse_date_from_header()

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
        if "Received" in self._message:
            date = parser.parse(self._message.get('Received').split(";")[1].strip()).date().strftime("%d/%m/%Y")
            return date

    def _get_message_snippet(self):
        self._message_info['Snippet'] = self._message['snippet']

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

    def _parse_body_part(self, msg):
        # multi-part emails often have both
        # a text/plain and a text/html part.
        # Use the first `text/plain` part if there is one,
        # otherwise take the first `text/*` part.
        body = self._message_info["Body"]
        main_content = None
        for part in msg.get_payload():
            is_txt = part.get_content_type() == 'text/plain'
            if not main_content or is_txt:
                main_content = self._parse_body(part)
            if part.get('Content-Disposition'):
                self._message_info["Attach_Num"] += 1
            if is_txt:
                break
        if main_content:
            body.extend(main_content)

    def _parse_text_content(self, msg):
        if msg.get_content_type() == "text/plain":
            self._handle_plain_text(msg)
        elif msg.get_content_type() == "text/html":
            self._handle_html_text(msg)
        else:
            raise TypeError("Unsupportable type")


if __name__ == '__main__':
    G = GmailAgent()
    while True:
        if G.scan_for_new_message():
            pprint.pprint(G.get_info_from_message())
            pprint.pprint(G.get_last_message_raw())
