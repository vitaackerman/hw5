# AI Prompt Log

## Problem 1 — Project setup

### First prompt

> im starting homework 5 for my ai class. like previous homeworks, please set up the project but dont solve any homework problems yet
>
> work one problem at a time. i will describ each problem to you in my own words before you work on it, so dont work ahead
>
> create `AI_prompts.md` and keep it updated throughout the homework
>
> for each problem, include:
>
> - the problem number and title
> - at least one prompt i actually typed to you in my own words
> - if i needed a follow-up, include only one follow-up prompt
> - if there was a follow-up, add one sentence explaining what was lacking after the first prompt
>
> when i give you a new problem, automatically add my prompt for that problem to `AI_prompts.md`
>
> dont add extra evidence sections
>
> this homework will eventually build a multiagent campus customs operations system with a boss agent plus inventory, accounting, facilities and customer service agents, but dont build any of that yet
>
> the provided `data/campus_customs.db` should remain untouched throughout the assignment. later work should use a separate working copy called `data/campus_customs_new.db`
>
> use only `gpt-6-luna` through my existing `PORTKEY_API_KEY` for ai model calls in this homework
>
> also add basic git housekeeping so secrets, `.env`, database files, cache files and other local-only files dont get committed later
>
> for now just set up the prompt log and basic project housekeeping, then stop

No follow-up prompt needed.

## Problem 2 — Study the database

### First prompt

> problem 2. study the campus customs database before we build any agents
>
> inspect every table and all of its fields in data/campus_customs.db, and look closely at the three open tickets so we understand how they connect to the other tables and what will eventually need to happen to resolve them
>
> make an exact copy of the original database as data/campus_customs_new.db. keep data/campus_customs.db untouched from now on because later problems should only modify the new working copy
>
> create output/harness.md. for every table, list its fields and add one short line explaining why that table matters for the agents
>
> also include a short section on the three open tickets and which tables/data seem relevant to each one, but dont solve the tickets yet
>
> verify that the original database and the new copy are identical immediately after copying
>
> update AI_prompts.md with this as my first prompt for problem 2
>
> dont work on future problems yet

No follow-up prompt needed.

## Problem 3 — Build the MCP server

### First prompt

> im working on problem 3. build the first version of the mcp server using fastmcp
>
> put it under `mcp_server/` and have it use only `data/campus_customs_new.db`, never the original database
>
> for now create 3 clear read-only tools that give the agents the information theyll need for the three open tickets:
>
> - a stock/restock lookup for a sku and size, so ticket 101 can check the unavailable white tee and ticket 103 can check hoodie inventory
> - a cash and upcoming obligations lookup that uses the relevant cash, invoice and lease data so ticket 102 can understand what is due and what cash is available
> - a pricing/margin lookup for a sku so ticket 103 can see cost, list price and the information needed to judge a bulk discount
>
> only return real information from the database and dont invent missing values
>
> use fastmcp and keep the tool ànames and arguments simple and obvious
>
> add `mcp_server/README.md` explaining what the server is for, that it uses `data/campus_customs_new.db`, and what the 3 tools do
>
> add a problem 3 section to `output/harness.md`. for each tool, say:
>
> - the exact table or tables it reads
> - which ticket it helps unlock
> - one sentence on whythat tool is useful for that ticket
>
> add any fastmcp dependency needed to the project requirements
>
> update `AI_prompts.md` with this as my first prompt for problem 3
>
> dont connect or run the mcp server yet because this problem doesnt require that

No follow-up prompt needed.

## Problem 4 — Connect and smoke-test the MCP server

### First prompt

> cool, now problem 4. connect the mcp server from problem 3 to this claude code project and test all 3 tools through the actual mcp connection
>
> create the project-level `.mcp.json` configuration and make sure it launches the server using the python environment where fastmcp is installed. use the existing `mcp_server/server.py` and `data/campus_customs_new.db`
>
> after connecting it, test each of the 3 mcp tools by actually calling them through claude, not by just calling the underlying python functions directly
>
> choose test promptstied to the real open tickets so the outputs are meaningful:
>
> - use the stock/restock tool for ticket 101 or 103
> - use the cash/obligations tool for ticket 102
> - use the pricing/margin tool for ticket 103
>
> save the evidence in `output/mcp_smoke.json`
>
> for each of the 3 tools include:
>
> - the prompt i asked the vbe coder
> - the exact mcp tool name
> - the arguments used
> - the tool output
>
> verify each tool output against `data/campus_customs_new.db` so the saved values are real and match the database
>
> dont modify the database while doing these smoke tests
>
> update `AI_prompts.md` with this as my first prompt for problem 4
>
> if claude code needs me to restart or reconnect the project before the new mcp server becomes available, stop and tell me exactly what i need to do rather than faking the tool tests

No follow-up prompt needed.

## Problem 5 — Build the agent team and expand the MCP server

### First prompt

> ok working on problem 5 now. build the full campus customs agent team and expand the mcp server so the agents have the tools they need for the open tickets
>
> create 5 pydanticai agents:
>
> - boss
> - inventory
> - accounting
> - facilities
> - customer service
>   
> i want the roles to work like this:
> - the boss is basically the manager of the whole shop. it should read the ticket, decide which specialist actually needs to be involved, delegate only the relevant parts, combine what the specialists tell it and make the final decision. it should be the only agent changing ticket status and it shouldnt automatically call everyone or repeat work another agent already did
> - inventory should own anything around what we physically have, what is missing, whether something can actually ship and how long a real restock would take. it should check actual stock, unpaid invoices and vendor lead times before saying something can ship or giving an eta
> - accounting should own cash, invoices, payment requests and discount/margin math. before recommending a payment it should look at other obligations too so we dont spend cash without understanding what else is due. it can prepare a payment request but it should never actually move money because that needs human approval. for discounts it should work out the economics and tell the boss the safe range, but the boss makes the final call
> - facilities should focus on the physical shop, especially the lease, rent and landlord issues. it should verify what is actually due and when, check whether theres enough cash, and it can prepare a rent payment request when thats needed, but it should never actually move money because that needs human approval. if theres a broader question about which bills should be prioritized or multiple obligations competing for the same cash, it should involve accounting instead of deciding that itself
> - customer service should turn the teams decisions into a clear and friendly customer response. it should only use facts that have actually been checked by the tools or another agent, never promise inventory or dates that arent confirmed, and never expose internal things like margins, unpaid bills or cash. it should only create drafts for a human to review and never contact anyone directly
> put one detailed prompt per agent in `backend/prompts/`, shared structured types in `backend/models.py`, and the agent code under `backend/`
>
> give the team full connectivity so any agent can delegate to any other agent when needed. the boss should read tickets, decide who should work on them and make the final calls
>
> use only `gpt-6-luna` through my existing `PORTKEY_API_KEY` for every agent
>
> all shop facts and database changes must go through the mcp server using `data/campus_customs_new.db`. dont create a second sqlite/tool layer inside the agents that bypasses mcp
>
> review tickets 101, 102 and 103 and add whatever additional mcp tools are actually needed for the agents to investigate and eventually resolve them. keep the original `data/campus_customs.db` untouched
>
> keep the shop rules from the assignment in the relevant agent prompts, especially:
>
> - use `desk.date_today` as today
> - vendor lead times come from the vendors table
> - dont ship product while theres still an open unpaid invoice for it
> - payments requiring human approval must not reduce cash or update payment records before approval
> - dont resolve a ticket until the database values have been rechecked
> - cash only goes out in this homework
> - dont email customers or call vendors, only create drafts
>
> make the agents append to `output/audit_trail.json` as they run. log each agent-loop step with enough information to audit which agent acted, delegations/tool calls, short results and stop reason, but dont store hidden chain of thought
>
> update `output/harness.md` with:
>
> - each agent and its role
> - every mcp tool and which database tables it uses
> - a short safety section for customer communication, inventory changes and real-money actions
> - practical limits that keep token/tool use bounded
>
> update `mcp_server/README.md` so its tool list matches the final mcp server
>
> update `AI_prompts.md` with this as my first prompt for problem 5
>
> dont resolve the three tickets yet. just build and test the team/tools enough to make sure the agents load, can delegate and can access the mcp tools correctly
>
> when youre done, tell me what you tested and whether theres anything i need to run myself

No follow-up prompt needed.

## Problem 6 — Desk tickets expected plan

### First prompt

> im working on problem 6. before running the agent team, build `output/desk_tickets.html` with one tab each for tickets 101, 102 and 103, plus empty `Cash` and `Reflection` tabs for later
>
> for each ticket tab, fill only an `Expected` section and leave room for an `Actual` section that well complete after the agents run
>
> base the expected plan on the real ticket and database facts we already studied
>
> for each ticket, explain:
>
> - which specialist the boss should call first and why
> - the specific sequence of agent delegations i expect after that, only involving agents that are actually useful for that ticket
> - the exact mcp tools i expect the agents to use
>
> use the actual agent roles and exact mcp tool names that exist in the current project, dont invent tool names
>
> the plans should be specific rather than saying the boss calls everyone
>
> for ticket 101, i expect the plan to focus on the out-of-stock customer order, the related restock/invoice issue and then any customer response needed
>
> for ticket 102, i expect the plan to focus on verifying the rent obligation, checking cash and other upcoming obligations, and respecting the human approval rule before any payment
>
> for ticket 103, i expect the plan to check whether 20 hoodies can actually be fulfilled, understand the margin/discount room, and then prepare an appropriate customer response
>
> dont actually resolve any ticket, call the agents, approve payments or modify `data/campus_customs_new.db` in this problem
>
> make `output/desk_tickets.html` clean and easy to read when i double click it
>
> update `AI_prompts.md` with this as my first prompt for problem 6

### Follow-up prompt

> i want to make 2 small corrections to the problem 6 expected plans before we run anything
>
> for ticket 102, facilities should verify the lease/rent obligation, but accounting should be the agent that checks cash and calls request_payment, since accounting is responsible for preparing payments for human approval. update the expected delegation sequence accordingly
>
> for ticket 101, keep the invoice 501 payment request as part of the plan because the unpaid vendor invoice is blocking the restock needed to resolve the customer order
>
> for ticket 103, dont state that the missing 12 hoodies will definitely arrive by 2026-09-05 unless the database/tools actually establish that a restock can be placed and that date follows from the vendor information. phrase the expected plan as checking the relevant stock, vendor and restock facts first, then determining the earliest feasible fulfillment date
>
> dont run any agents or modify the database. only update the expected sections in output/desk_tickets.html
>
> log this as my one follow-up for problem 6 in AI_prompts.md and add one sentence saying the first version put the rent payment action under facilities and was too certain about the hoodie restock date

The first version put the rent payment action under facilities instead of accounting and was too certain that the missing hoodies would arrive by 2026-09-05.

## Problem 7 — FastAPI backend routes

### First prompt

> im working on problem 7. build the fastapi backend routes that the dashboard will use
>
> put the api in `backend/main.py`
>
> add routes that:
>
> - return tickets 101, 102 and 103 with their current status
> - take a ticket id and run the existing agent team on that ticket
> - return recent agent events so the future dashboard can show which agents acted, what they said and which mcp tools they used
> - approve a pending payment or purchase only after a human explicitly calls the approval route. this route is what should actually change cash/payment state, not the agents themselves
> - return the current checking balance from `cash_accounts`
> - reset `data/campus_customs_new.db` back to the original values in `data/campus_customs.db`
>
> keep all shop database access by the agent team going through the mcp server. dont duplicate the mcp shop tools inside fastapi just to make the routes work
>
> make the route responses structured and useful for the react dashboard well build next
>
> make sure the backend runs from inside `backend/` with:
> `uvicorn main:app --reload --port 8000`
>
> dont do the final real run of tickets 101, 102 and 103 yet. test the read-only routes and route wiring, but leave the working database in its original reset state when youre done
>
> update `output/harness.md` with a problem 7 section listing every route in one line with its url/method and what it does
>
> update `AI_prompts.md` with this as my first prompt for problem 7
>
> when youre done, tell me which routes you tested and whether i need to run anything myself

No follow-up prompt needed.

## Problem 8 — React agent dashboard

### First prompt

> im working on problem 8. build the react + vite + typescript agent dashboard in `frontend/` and connect it to the fastapi backend already running at `http://localhost:8000`
>
> make sure the backend allows the vite origin, normally `http://localhost:5173`
>
> the dashboard should:
>
> - show all 3 tickets and their current status
> - let me select one ticket and start the agent team on it
> - show the agents working in real time while the run is happening, including which agent is active, what its doing/saying and which mcp tools it uses
> - show a short summary of what each agent did when the run finishes
> - reflect the tickets resolved/current status from the backend rather than faking state only in the frontend
> - show pending payment or purchase approvals and let a human approve them
> - show the current checking balance and visibly update it after an approved payment
>
> use the routes from problem 7 rather than creating a second backend
>
> make the dashboard visually distinctive and polished. i want it to feel like an actual campus customs operations desk that a human manager would enjoy using, not a generic admin template. use clear visual differences between the boss and specialist agents, make ticket states and human approvals easy to understand, and make cash prominent
>
> keep the interface understandable while agents are running, with useful loading/running states and no duplicate run clicks
>
> create `output/design.md` explaining the dashboard layout, how the agents are visually distinguished, how resolved tickets and cash are shown, and the creative choices that make the desk useful and enjoyable
>
> update `AI_prompts.md` with this as my first prompt for problem 8
>
> during development you can test the api/dashboard, but dont leave the working database in a partially modified test state. reset it when youre done if needed
>
> when youre done, tell me whether the frontend is already running and exactly what i should test in the browser

No follow-up prompt needed.

## Problem 9 — Real full run of the three tickets

### First prompt

> this is the real full run of the three tickets
>
> before doing anything, reset `data/campus_customs_new.db` to the original database values using the reset flow from problem 7 and record the starting checking balance
>
> then run tickets 101, 102 and 103 through the real agent team and real mcp tools until each ticket is resolved
>
> use the actual backend/dashboard flow we built, not a fake model or test database
>
> very important: if an agent creates a payment or purchase request that requires human approval, dont approve it yourself. pause and tell me exactly which request is waiting, the amount, what its for, and what i need to click in the dashboard. after i approve it myself, continue the ticket and let the agents recheck the database before resolving it
>
> dont bypass the human approval rule or directly edit the database to make a ticket resolve
>
> keep appending the real agent activity to `output/audit_trail.json`
>
> after each ticket finishes, update its `Actual` section in `output/desk_tickets.html` while keeping the existing `Expected` section. include:
>
> - which agents actually worked
> - what they delegated to each other
> - which mcp tools they actually used
> - what decision/action ultimately resolved the ticket
> - any human approval that was required
>
> fill the `Cash` tab in the same file with:
>
> - starting checking balance after reset
> - for each ticket, exactly how cash changed when that ticket was resolved and why, including the payment or purchase and dollar amount
> - ending checking balance, verified directly against `cash_accounts`
>
> dont assume the cash math from our earlier planning. use the actual approved actions from this run and verify the final balance against the database
>
> create `output/resolved_tickets.json` with one entry per ticket containing its id, final status, short outcome, what each agent contributed and any human approvals
>
> create `output/resolved_board.html` with a screenshot of the real react dashboard for each resolved ticket 101, 102 and 103. use real screenshots from this run and relative paths so the html can be double clicked
>
> finish `output/harness.md` so it covers the database tables, all mcp tools, all 5 agents, api routes, dashboard, audit trail and safety rules
>
> update `AI_prompts.md` with this as my first prompt for problem 9
>
> start the real run now, but stop whenever human approval is required and tell me exactly what i need to approve before continuing

No follow-up prompt needed.

## Problem 10 — Reflection

### First prompt

> ok working on problem 10 now. fill the Reflection tab in `output/desk_tickets.html` based on the actual runs we just completed
>
> please use the evidence already in:
> - the Expected and Actual sections of `output/desk_tickets.html`
> - `output/resolved_tickets.json`
> - `output/audit_trail.json`
> - the Cash tab
> - `output/harness.md`
>
> write this mimicing my vibe, not like a polished AI essay, but still capitalize the first letters of sentences please, not like ido. i want it to sound like a student actually looking at what happened and thinking about whether the multi-agent setup was useful. it can be detailed but should be direct and a little conversational
>
> answer all 5 questions from problem 10:
>
> 1. evaluate how the agents performed on each ticket and why
> 2. compare Actual to Expected for each ticket
> 3. explain what would have been simpler as one agent with tools and why
> 4. give 3 new Campus Customs problems this existing team could solve with the tools we already built
> 5. give 3 new problems it could not solve, and explain what new tools and/or agents would be needed
>
> for my evaluation, use these judgments as the basis but you can expand:
>
> -for ticket 101, i think it worked pretty well overall but was more complicated than it needed to be. the agents got the important things right: inventory saw there were 0 size S shirts, accounting dealt with the $840 invoice request, customer service drafted the message, and nothing got shipped when there was no stock. but it took 3 runs and we had to figure out what “resolved” even meant since the shirts hadnt actually arrived yet  for ticket 102, i think this is the clearest example where having multiple agents was kind of unnecessary. facilities checked the rent and then also checked the cash and made the payment request, while accounting mostly checked the same cash situation again. it still worked and i still had to approve the $2,400 payment myself, but one agent with the right tools probably could have done this whole thing  for ticket 103, i think having multiple agents made more sense because there were actually different questions to answer: inventory had to check if we could supply 20 hoodies, accounting had to look at the discount and margin, the boss had to choose the discount, and customer service had to write the final response. but it still got a little messy because customer service tried to delegate back to the boss, that got blocked, and we ended up with an outdated draft before the final one  my overall takeaway is basically that multiple agents are useful when the jobs are actually different, but if the task is simple it can just create extra steps and duplicate work. i also thought the safety parts worked better than the coordination parts. i had to approve payments myself, messages stayed as drafts, the agents couldnt invent stock, and they couldnt just move money on their own  for the question about what would have been simpler with one agent, definitely use ticket 102 as the main example. you can also mention that parts of 101 probably could have been done by one general operations agent with the same tools  for 3 new problems the current team could solve, use things that are actually similar to what the tools already do  for 3 things the current team could not solve, we could say like: - adding stock to inventory - adding money to cash - processing a return or refund. explain simply what new tools or agents would be needed
>
> for each unsupported problem, explain what would need to be added. for example a procurement/receiving agent and receive_stock tool, a sales/order agent with order and cash-in tools, or a returns agent with return/refund tools
>
> tie every answer to THIS app and the 3 tickets you ran, use ther ticket tabs and cash tab on the same page as your evidence. dont invent extra events or tools
>
> also update `AI_prompts.md` with this as my first prompt for problem 10. dont add a follow-up unless i actually give you one

No follow-up prompt needed.

## Problem 11 — Final GitHub submission

### First prompt

> ok working on problem 11 now. im giving you the screenshot of the required final github structure
>
> compare my current hw5 project to that structure and fix only actual submission issues
>
> make sure:
>
> - the repo matches the required structure in the screenshot
> - both database files under `data/` are included
> - my real `.env`, api keys, `.venv`, `node_modules`, `__pycache__`, `.pyc`, `.DS_Store` and other temporary files are not pushed
> - `.env.example` only has placeholders
> - any screenshots/files used by `output/resolved_board.html` are included and the relative paths work
> - the problem 10 Reflection tab is filled in `output/desk_tickets.html`
> - `README.md` explains how a grader can set up and run the mcp server, backend and frontend and reset the database for a clean run
>
> dont change the actual agent logic or completed outputs unless theres a real submission problem
>
> then push the finished project to a public github repo, save the public repo url in `output/github_url.txt`, and verify the remote repo actually contains everything required
>
> update `AI_prompts.md` with this as my first prompt for problem 11
>
> when youre done tell me the github url and whether theres anything i still need to do before submitting it on canvas

No follow-up prompt needed.
