# AI Prompts Log — HW 4 (Campus Customs Website)

Every prompt given to the AI assistant for this assignment, recorded verbatim and in order.

---

# Setup

## Prompt 1
> Today we are making a website for Campus Customs. Start in the homework 4 folder.

## Prompt 2
> Now wait for my instructions.

## Prompt 3
> Create a .vnv-safe environment to start with. Record everything that I'm saying into an ai_prompts.md file so that you record every prompt that I tell you in that.

---

# Problem 2 — Database

## Prompt 1
> In the prompts.md file, start this as problem 2 and then put all the prompts I'm telling you now under that. In problem 2, we will be looking at the database. There is data in the folder that I have shared with you. Look at that and understand each field in each table.

## Prompt 2
> Put the results in outputs. First of all, start with converting all the tables that you have read into JSON files so that it is easy for the code to read it.

## Prompt 3
> Now put an output/harness.md file. In this, read all the key elements from the JSONs, like:
>
> * catalog
> * inventory
> * users
> * chat messages
>
> so that we can use that on the website later. I think the most important would be the catalog because that is what will be on the website. The inventory is important because how will we show the customers what the current inventory is at Campus Customs. Users and chat messages can be kept for later, but let's see if we have to put that on the website.

## Prompt 4
> Okay, now before we proceed to the frontend, check that you have all packages in place for the backend.

---

# Problem 3 — Frontend

## Prompt 1
> Now, the next set is in problem 3. We are creating a frontend for the campus customers' website. Make a React app. It has to have a white and TypeScript frontend. Do all the packages. Keep all the packages in you.
>
> Make the frontend such that it has the links to the main pages:
>
> * Home
> * Products catalog
> * About us
> * Login
> * Create account
>
> Keep these as tabs on the main page at the top. I will also give you a reference link from where you can see more about what a website looks like.

## Prompt 2
> Pull campus customs like wordings from yalebulldogblue.com, do not copy stuff, take references.

## Prompt 3
> On the products page, show product images from the catalogue

## Prompt 4
> Along with that it should have basic product infor like name, price, short description of the product

## Prompt 5
> Make each item click into a single item page with all the details there like a typical website - large image on the right, full size text on the other including sizes, product description, etc.

## Prompt 6
> Next after you're done, Can we now add a small chat option to the bottom, that is not linked to an AI agent yet but has FastAPI to connect with the database from the backend

---

# Problem 4 — Accounts & Login

## Prompt 1
> now onto problem 4 where we will create a basic account and login flow. once accounts are created, details go into users table. also secure the passwords so no one can hack them

## Prompt 2
> Now, the database that you have already has a test user, so use that to test out whether, from the email and the password, a user is able to log in and whether a brand-new account can also be created. Do this one by one and give me the results.

---

# Problem 5 — AI Chatbot

## Prompt 1
> Now, till the time you run it, we are doing another task: problem 5. Here, we have to build the chatbot as a Pydantic AI agent behind Fast API. Plug it into your frontend chat widget. Then lets take it from there

## Prompt 2
> Now put the API app in backend/main.py. That is where the file will run with uvicorn. In main.py, expose the chat route so a message from the website returns a reply from the agent. Something like: "What do you need today? What products are you looking for?" Maybe a dropdown of the key questions that people may ask.
>
> For the AI model, the AI agent: use OpenAI's ChatGPT, Luna 5.5, using my port key API key. Keep everything safe. Also create a backend/prompt/prompt.md file so that everything that we do is logged.

## Prompt 3
> Put campus customs, voice, and safety basics into the prompts/prompts.md. We need the chat to be secure, and everything in the agent to be secure. Things that we constantly do, keep that updated in models.py. Any chat replies, any new product cards. Start with that.

## Prompt 4
> run this in terminal uvicorn main:app --reload --port 8000

---

# Problem 6 — Agent Tools

## Prompt 1
> Now, on to problem 6. We will be giving the agent that we've built tools so that it can look up real information from the campus customs database that we have. It should never invent any of the prices or quantities. Build tools in tools.py for the agent for getting product description, price, and how many things are in stock when somebody prompts these things in the chatbot.

## Prompt 2
> Now, we have to include stuff in prompt/prompt.md so the agent knows when to call these tools for price and any related questions the customer puts in. For each tool that we have here, link it to an attribute in the database. For example, something like "How much is the basic hoodie bag?" will use the find tool to get the price. Similarly, for "How many Yale hoodies are there?", it will go to the particular hoodie and do the get stock attribute.
>
> If you have not done this already, put each of these things into the prompts file and then update models.py if that's not already done. In output/harness.md, list each tool and explain which model fields we have chosen for getting which of the results and why.

---

# Problem 7 — API Contract

## Prompt 1
> Now, on to problem 7. Here, we are doing an API contract. For example, if a customer asks, "What hoodies do you have?" the agent has to search the catalog and display to the customer the matching items as product cards when somebody types that into the chat. The agent is going to do structured product matches, and then, from the backend, it is going to be rendered on the frontend of the website in the chat.

## Prompt 2
> Make sure that these things that we're doing are for the agent, but everything that we built earlier around people clicking the products on the website and it loading to a new page entirely should still work. These are two independent things.

---

# Problem 8 — Saved Chat History

## Prompt 1
> When a shopper is logged in, save their chat history in the database appropriately and reload when they return. The agent should know who is chatting (name, email). Use a tool that the agent can call to fetch these information from where we stored account informations after creation

## Prompt 2
> This history needs to be only stored for the people that are logged in. New guests will still be able to chat on the website. Put in output/harness.md the ways that chat history is stored, basically everything that we have already mentioned in this problem. Also, this was problem 8, so just edit that as well.
>
> Everything that the agent sees needs to be there. The agent also needs to have enough context from the page. If somebody asks, "Do you have this in pink?" they should know what the chat was about and if it was the hoodie that they were talking to about. If you showed them a picture in blue, the agent should know. Don't screw up.

---

# Problem 9 — Front-end Improvements

## Prompt 1
> Now onto problem 9, we need to suggest 2 front-end improvements

## Prompt 2
> fix the 2 things

## Prompt 3
> Also put these usability improvements made to both frontend and backend into output/usability.md to show what you added, why it helps a Campus Customs shopper or the business

---

# Problem 10 — Yale Blue Theme & Bulldog Chatbot

## Prompt 1
> Now for problem 10, make the website have blue colour like Yale and Campus Customs colour to make it appealing, make the chatbot have a bulldog which is the official Yale mascot

## Prompt 2
> In output/design.md write that we changed the colour of the website to be more aligned with the official Yale and Campus customs colours, adding the bulldog adds the true feeling of being at Yale into the website and also differentiates it from any other fake websites. students that I have talked to love the bulldog so more likely to talk.

---

# Problem 11 — Live Testing

## Prompt 1
> Lets now live test the app in problem 10 and test the outputs in output/app_check.html

## Prompt 2
> give me the site link to run it myself on a browser

## Prompt 3
> Testing and also the above task is actually problem 11 so put it under that. The above are screenshots I have taken from our site, put these screenshots in output/app_check_images and link them from app_check.html with relative paths to show what each represent in terms of the great work we have done. Log that into the output md file

*(7 screenshots attached, saved to `outputs/app_check_images/`)*

---

# Problem 12 — Agent Audit Trail

## Prompt 1
> Keep an append-only output/audit_trail.json of agent-loop activity that shows time, too name, short args/result, stop reason

## Prompt 2
> This is problem 12

## Prompt 3
> Now finish output/harness.md so it is clear how the system works, model fields in models.py, tools and abilities, safety rules, specs like loop limits, result caps, models, how to run front + back

---

# Problem 13 — Publish to GitHub

## Prompt 1
> for the last problem 13: put all the the code we wrote today in hw4 folder and push it to linked GitHub repository. Do not put my .env file, db or any sensitive info into the public repository, use Gitignore for all this. never ever send the api key

## Prompt 2
> check if everything works correctly in the repo as I have submitted it
