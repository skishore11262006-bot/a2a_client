# A2A (Agent-to-Agent) Integration — Local Agent

Google A2A is an open protocol that lets AI agents discover each other
and exchange tasks over HTTP using JSON-RPC 2.0.

## What is A2A

- Agent Card: a JSON file that describes an agent (name, skills, endpoint)
- Task: a unit of work sent from one agent to another
- Transport: HTTP POST with JSON-RPC methods
- Methods: message/send, message/stream, tasks/get, tasks/cancel
- Streaming: Server-Sent Events (SSE) for live updates

## How it works

1. Client agent fetches the remote agent card
   GET http://host:port/.well-known/agent.json
2. Client sends a task
   POST <agent.url>  { method: "message/send", params: { message: {...} } }
3. Server agent runs its own agent loop and returns a Task object
4. Task state moves: submitted -> working -> completed | failed | canceled
5. Result text lives in task.artifacts[].parts[].text

## Files in this project

- backend/a2a_server.py  -> exposes YOUR agent as an A2A server
- backend/a2a_client.py  -> talks to ANY other A2A agent

## Setup (Server side)

1. In backend/main.py add:

   from a2a_server import router as a2a_router
   app.include_router(a2a_router)

2. Start the server:

   cd backend
   pip install fastapi uvicorn requests
   python -m uvicorn main:app --port 8001

3. Verify the agent card:

   http://127.0.0.1:8001/.well-known/agent.json
   http://127.0.0.1:8001/a2a/tasks   (list of tasks)

## Setup (Client side)

Simple request:

   from a2a_client import A2AClient

   c = A2AClient("http://127.0.0.1:8001")
   c.discover()                 # load agent card
   task = c.send("read hello.txt")
   print(c.reply_text(task))

One-liner:

   print(c.ask("what files are in my folder?"))

Streaming (SSE):

   for event, data in c.stream("search the web for weather"):
       print(event, data)

Continue a conversation (same task/context):

   t1 = c.send("hello")
   t2 = c.send("and now list files",
               task_id=t1["id"], context_id=t1["contextId"])

Check / cancel:

   c.get_task("task_id")
   c.cancel_task("task_id")

Run from terminal:

   python a2a_client.py http://127.0.0.1:8001 list my files

## Connect two of your own agents

1. Run agent A on port 8001 (server)
2. Run agent B on port 8002 (server)
3. From agent B, call agent A:

   from a2a_client import A2AClient
   other = A2AClient("http://127.0.0.1:8001")
   result = other.ask("do this subtask for me")

4. Or expose a route on agent B so agent A can call it back.
   Two agents can now delegate tasks to each other.

## Message format

Request:
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "kind": "message",
      "role": "user",
      "messageId": "abc123",
      "taskId": null,
      "contextId": null,
      "parts": [{ "type": "text", "text": "your task here" }]
    }
  }
}

Response:
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "kind": "task",
    "id": "task_id",
    "status": { "state": "completed" },
    "artifacts": [{ "parts": [{ "type": "text", "text": "reply" }] }],
    "history": [ ... ]
  }
}

## Full A2A method list (spec 0.2)

- message/send     send a task, get the Task back
- message/stream   send a task, get SSE events (task, task_status_update, task_message_update)
- tasks/get        query task status/result
- tasks/cancel     cancel a running task
- tasks/resubscribe  resume streaming on a task
- pushNotificationConfig/set   register a webhook URL (optional)

## Agent Card fields

{
  "protocolVersion": "0.2",
  "name": "Local Agent",
  "description": "...",
  "url": "http://127.0.0.1:8001/a2a",   <- JSON-RPC endpoint
  "version": "1.0.0",
  "capabilities": { "streaming": true, "pushNotifications": false },
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  "skills": [{ "id": "chat", "name": "...", "description": "...", "tags": [] }]
}

## Flow diagram

User -> Local Agent -> A2A Client -> HTTP -> Remote Agent (A2A Server)
                                              -> runs run_agent()
                                              <- returns Task with reply
Local Agent -> User

## Notes

- No authentication in this version. For public use add
  an Authorization header and set "capabilities.requiresAuth" in the card.
- Tasks are stored in memory only (a2a_server.TASKS).
  Add a database if you need persistence.
- For multiple remote agents, create one A2AClient per agent URL
  and let the model choose which one to call as a tool.

## Official references

- Spec: https://a2a-protocol.org/latest/specification/
- GitHub: https://github.com/a2aproject/A2A
- Agent Card: /.well-known/agent.json
