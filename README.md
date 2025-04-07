### Budget-tracking-bot.

To provision it, its an AWS SAM framework, just perform:

Build the app first:
1. enter `budget-bot` folder, perform `sam build`
2. then deploy the stalk - `sam deploy --config-env dev --no-confirm-changeset --no-fail-on-empty-changeset`

You can use Makefile to perform similar quick actions.