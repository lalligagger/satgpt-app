**Introduction**

This is a demo web app for `SatGPT`, an experimental project that uses large language models (LLMs) to retrieve and generate satellite data.

So far, the app can help retrieve Sentinel 2 optical imagery based on the user's requested area and time of interest in natural language. It is built on the following:

* OpenAI ChatGPT API
* LangChain
* STAC & Element84 EarthSearch
* Panel


**Getting started**

1) Fork this repo
    - From the repo site on GitHub, you'll want to create your own fork of this project
2) Add API key(s)
    - From your forked repo, go to "Settings" > "Secrets and variables" > "Codespaces"
    - Add your OpenAI API key as a new repository secret
    - Use `OPENAI_API_KEY` as the Name (`YOUR_SECRET_NAME`), and put the key in the Secret field
3) Launch Codespaces
    - Start a Codespace from the main page of your repo, using the "Code" dropdown and the "Codespaces" tab
    - The Codespace will install all requirements, which will take a few minutes; once the environment is ready, you can launch the app
    - Typically, a panel app is launched using `panel serve app.py`; in Codespaces the port that the app runs on will be automatically forwarded, but we need to add one extra argument to allow the app to communicate with itself...
    - The argument is `--allow-websocket-origin=...` and will be equal to one of two values depending on how you decided to run the Codespace:
        - If you are running the Codespace remotely (in your browser), you'll want to note the subdomain that your Codespace launched to, the full command will be:
        
        `python -m panel serve app.py --allow-websocket-origin=YOUR_SUBDOMAIN-5006.preview.app.github.dev`
        - If you are running in VSCode desktop, you'll want to use localhost:

        `python -m panel serve app.py --allow-websocket-origin=http://127.0.0.1:5006`

**Looking ahead**

SatGPT was originally built on the OpenAI API without LangChain tools/ agents, using a single prompt and one or two custom CLI tools. It used ShellGPT for automatic execution in a shell REPL and could generate STAC item searches as well as save TIFs or GIFs of the search.

In the future, we would like to re-integrate all of that functionality into a future version of SatGPT built on LangChain and a library of tools specific to satellite image analysis and mission engineering.