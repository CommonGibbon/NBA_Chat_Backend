-- This is bascially our database setup run book, it tells the db what tables to create and it runs similar to a one-time-use script

CREATE TABLE chats (
    id UUID PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    chat_id UUID REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT CHECK (role IN ('user','assistant', 'system')) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- create a chat_id -> created_at index to speed up query time, this way if we query for messages in a chat, we can quickly pull them rather than
-- scanning the entire table to accumulate a list of the correct chats. Similar for created_at subindex. 
CREATE INDEX idx_messages_chat_created ON messages(chat_id, created_at);
