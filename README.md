# LynX: Solana Trading Bot for Telegram

LynX is a powerful, automated Telegram bot built in Python for managing and executing token trades on the Solana blockchain. It leverages asynchronous programming, PostgreSQL for persistent storage, and the Jupiter API for secure swaps—all through an intuitive Telegram interface.

## Table of Contents

- [Features](#features)
- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Wallet & Agent Management:**  
  - Create, import, export, and delete a *Root Wallet* (the main treasury).  
  - Create up to 10 *Agent Wallets* to automate trading with custom settings.
  
- **Automated Trading Cycle:**  
  - Continuously execute buy/sell cycles using configurable parameters (fixed buy amount, sell delay, slippage, etc.).
  
- **Jupiter API Integration:**  
  - Fetch swap quotes and execute transactions securely on the Solana blockchain.
  
- **Database Integration:**  
  - Use PostgreSQL (via `asyncpg`) to store wallet information and trading configurations persistently.
  
- **User-Friendly Telegram Interface:**  
  - Interactive commands and inline keyboards (powered by `aiogram`) guide users through setup and trading operations.

## Overview

LynX simplifies and automates token trading on Solana through a familiar Telegram chat interface. Key highlights include:

- **Initialization:**  
  When a user sends the `/start` command, the bot initializes the database, sets up referral information (if provided), and displays a main menu for further actions.

- **Wallet Management:**  
  - **Root Wallet:** Acts as the main treasury for managing funds.
  - **Agent Wallets:** Each agent is configurable with parameters like fixed buy amounts, sell delays, slippage settings, and more. Users can even copy settings from an existing agent.

- **Automated Trading:**  
  Each agent continuously monitors its SOL balance. When the balance reaches the required threshold, the bot executes a buy order via the Jupiter API. After a configurable delay, if enabled, a corresponding sell order is executed, completing the trading cycle.

- **Jupiter API Integration:**  
  Functions such as `jupiter_get_quote` and `jupiter_swap` handle retrieving swap quotes (with rate-limit handling) and executing signed transactions on the Solana network.

- **Persistent Settings:**  
  Global and agent-specific settings (like slippage, fixed buy amounts, and referral details) are stored in PostgreSQL, ensuring configurations persist across bot restarts.

## Architecture

LynX is built with modern Python async frameworks and consists of the following core components:

- **Telegram Bot Interface (`aiogram`):**  
  Manages commands (e.g., `/start`, `/wallet`, `/agents`) and interactive menus.

- **Asynchronous Processing (`asyncio`):**  
  Enables non-blocking operations for network requests and blockchain transactions.

- **Database Connectivity (`asyncpg`):**  
  Handles PostgreSQL operations for wallets and settings.

- **Solana & Jupiter API Integration:**  
  Facilitates token swaps by fetching quotes and submitting signed transactions.

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/lynx.git
   cd lynx
