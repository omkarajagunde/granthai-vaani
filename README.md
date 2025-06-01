# Vaani | वाणी 🎙️🌐

> **AI Phone Agents that sound human, speak any language, and work 24/7.**

---

### ✨ Overview

**Vaani** (वाणी) is your AI-powered phone assistant that sounds natural, understands context, and communicates in **any language**—ready to serve your business 24x7.

While we’re a wrapper on top of powerful services like **Google Gemini** and **ElevenLabs**, our real value lies in making it all *work seamlessly* for **real businesses**. Think of us as your **AI agent setup partner**—from voice to integrations to deployment.

<iframe width="560" height="315" src="https://www.youtube.com/embed/4etad9Lx9YY?si=snEj5vWxq_Y82Ybh" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

---

### 🏥 Example Use Case: Pathology Test Booking Agent

In the healthcare space—particularly **pathology labs**—many patients still **call in** to book appointments for blood work.

We built an MVP to automate this entire process using AI agents that:
- Answer patient calls
- Provide test package information
- Book appointments for home sample collection

👂 **Talk to the agent yourself**:  
🔗 **[Live Demo](https://granthai-vaani.vercel.app/)**

#### 🛠️ Agent Tools
Our Gemini agent interacts with these tools to perform actions:

- 📦 [`get_health_packages`](https://github.com/omkarajagunde/granthai-vaani/blob/master/backend/tools.py#L4)  
- 🔍 [`get_test_details`](https://github.com/omkarajagunde/granthai-vaani/blob/master/backend/tools.py#L16)  
- 📅 [`book_appointment`](https://github.com/omkarajagunde/granthai-vaani/blob/master/backend/tools.py#L28)

---

### 🧠 Tech Stack

- **Frontend**: Auto-generated with [v0.dev](https://v0.dev), hosted on [Vercel](https://vercel.com/)
- **Backend**: Python + websockets, hosted on [Railway](https://railway.app/)
- **AI Model**: `gemini-2.0-flash-live-001` via [Google Gemini SDK (Python)](https://pypi.org/project/google/)
- **Voice**: Gemini's speech-to-speech APIs
- **CI/CD**: Deployed via GitHub Actions on `master` branch push

---

### 🎥 Credits & Inspirations

- 💡 Inspired by real-world business workflows
- 📚 Used ChatGPT to generate best expressive prompts
- 📺 Huge shoutout to [YeYuLab on YouTube](https://www.youtube.com/@yeyulab)  
  > His videos made working with Gemini Live API *so much easier!*

---

### 👥 Contributors

| Name | GitHub | Contribution |
|------|--------|--------------|
| **Elson Nag** | [@ElsonNS](https://github.com/ElsonNS) | UI & UX with v0.dev |
| **Rahul Kumar Sah** | [@rahul-4321](https://github.com/rahul-4321) | Integration with Gemini & ElevenLabs |
| **Omkar Ajagunde** | [@omkarajagunde](https://github.com/omkarajagunde) | Tool definitions, prompt engineering, agent orchestration |

> 💬 We heavily used **ChatGPT** throughout the journey—for debugging, brainstorming prompts, and refining interactions.

---

### 🛣️ Roadmap (Next Steps)

- 🔄 Switchable models: Toggle between Gemini & ElevenLabs voice engines
- 🧠 Context memory: Save user history across sessions
- 📞 Twillio integration: So that users can directly have call with assitant

---

### 📞 Want Vaani for your Business?

We're actively onboarding early adopters.  
Get in touch and let’s automate your voice operations with human-sounding AI agents!

---

### 📄 License

MIT – do whatever you want, just don't forget to credit the builders 😉

---

