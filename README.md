**Introduction**

This is a demo web app for `SatGPT`, an experimental project that uses large language models (LLMs) to retrieve and generate satellite data.

https://github.com/lalligagger/satgpt-app/assets/11700267/8675bdc5-ca40-418e-98ce-724ec06ad05a

So far, the app can help retrieve Sentinel 2 optical imagery based on the user's requested area and time of interest in natural language. It is built on the following:

* [OpenAI ChatGPT API](https://openai.com/blog/openai-api) - You've probably tried the chat bot... if you haven't played with the API, you should!
* [LangChain](https://python.langchain.com/en/latest/index.html) - LangChain provides abstractions and common tooling for many LLMs, including OpenAI; this project uses the recently released structured tools to facilitate API requests in natural language
* [STAC](https://stacspec.org/en) & [Element84 EarthSearch v1](https://www.element84.com/blog/introducing-earth-search-v1-new-datasets-now-available) - The spatiotemporal asset catalogs (STAC) specification is a common way to describe geospatial information; Element84 has launched their version 1 EarthSearch catalog to make public satellite imagery more available and discoverable
* [Holoviz Panel](https://panel.holoviz.org/) - A python-friendly app development package that works well with the greater Holoviz data & vizualization ecosystem


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
    - Typically, a panel app is launched using `python -m panel serve app.py`; in Codespaces the port that the app runs on will be automatically forwarded, but we need to add one extra argument to allow the app to communicate with itself...
    - The argument is `--allow-websocket-origin=...` and will be equal to one of two values depending on how you decided to run the Codespace:
        - If you are running the Codespace remotely (in your browser), you'll want to note the subdomain that your Codespace launched to (everything ahead of the `github.dev` in your browser address bar), and add `-5006.preview.app.github.dev` to that; the full command will be:
        
        `python -m panel serve app.py --allow-websocket-origin=YOUR_SUBDOMAIN-5006.preview.app.github.dev`
        - If you are running in VSCode desktop, you'll want to use localhost:

        `python -m panel serve app.py --allow-websocket-origin=127.0.0.1:5006`

Note: you only need to set this up once. All GitHub accounts now come with 60 CPU hours (30 hours on a 2-CPU instance) of Codespaces use per month. All git commands and authentication should "just work" for your fork, and files will be saved in between commits. It will likely remain the top-supported deployment for SatGPT, which will require the management of one or more individual API keys for users. Further instructions will be provided on how to keep your instance up to date without going through a full rebuild.

**Looking ahead**

SatGPT was [originally](https://github.com/lalligagger/satgpt) built on the OpenAI API without LangChain tools/ agents, using a single prompt and one or two custom CLI tools. It used [ShellGPT](https://github.com/TheR1D/shell_gpt) for automatic execution in a shell REPL and could generate STAC item searches as well as save TIFs or GIFs of the search.

In the future, we would like to re-integrate all of that functionality into a future version of SatGPT built on LangChain and a library of tools specific to satellite image analysis and mission engineering. It'd also be nice to run on LLMs that don't rely sending data to external APIs, which will be possible with LangChain.
