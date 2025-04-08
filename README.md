### Budget-tracking-bot.

Budget tracking bot is a simple friendly chatbot, you just say your expenses as like friendly chat. 
for eg: `paid rent 17k`, `taxi 400`, that's all, it will save your expenses and will gives you back whenever you ask it.

this will auto-catogories the expenses and sends alerts to you when you reached your limit of threshold, the threshold can be set further by you.

- we know that typing is a pain, moving further we're aim to make it much more smart. and to use it for now, we just integrated it with telegram bot, where you can interact with it. 

does we need telegram compulsory, Definitely NOT!, we're able to integrate with WhatsApp and other meta apps as well.

For more about product: Just have quick look at this [blog](https://krupakar.in/blogs/llm/bedrock_integrated_budget_bot) :)

---

#### Usage:

This is completely using serverless components, we build using SAM framework which would be easy for developing locally and deploy remotely. 

it had `makefile` to utilize.

1. this folder had infrastructure named folder having [dynamodb-table](./infrastructure/dynamodb-table/) and apply terraform, it will provision the table for storing your expenses data.

2. Next, after creation of table, just come to [budget-bot](./budget-bot/) folder and perform `make deploy`, this will deploy sam with required polices and setup - lambda and its logs, api-gw with custom dns attached.

3. finally configure 2 environments vars for the lambda for now - GEMINI-API_KEY and telegram bot key.

4. Finally attach/integrate telegram bot to your custom dns.
for eg: 
`curl -X POST "https://api.telegram.org/bot7231070881:AAFPwGvrniLcsRYv-HYBvmsZfwheBoMhOJY/setWebhook" -d "url=https://budget.app.krupakar.in/tracker/"`

that's all! you're all set!!