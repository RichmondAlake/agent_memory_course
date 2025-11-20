# Agent Memory Course

[Course Presentation](https://docs.google.com/presentation/d/1fMb6Z0HcwjmN_BT4-HhRHHQ1ysohlzDzYDOg-Foldrc/edit?slide=id.p1#slide=id.p1) | [Agent Memory Discord Server](https://discord.gg/kGs5hKy8n8)

This repository contains companion code and examples for the **AI Memory Management in Agentic Systems** course.

## Course Link

This is the companion code to the course: [AI Memory Management in Agentic Systems](https://learning.oreilly.com/live-events/ai-memory-management-in-agentic-systems/0642572179274/)

Viewers can access the course to watch the recording of the instructor going through each notebook and explaining the concepts in detail.

## Libraries and Corresponding Notebooks

| Library/Approach | Notebook | Description |
|------------------|----------|-------------|
| **Information Retrieval** | [`parrt1/information_retrieval/zero_to_hero_with_genai_with_mongodb_openai.ipynb`](information_retrieval/zero_to_hero_with_genai_with_mongodb_openai.ipynb) | Zero to hero guide using MongoDB and OpenAI for generative AI applications |
| **LangMem** | [`part1/langmem/memory_augmented_agent_with_mongodb.ipynb`](langmem/memory_augmented_agent_with_mongodb.ipynb) | Memory-augmented agent implementation using MongoDB |
| **Mem0** | [`part1/mem0/memory_augmented_agent_with_mem0_mongodb.ipynb`](mem0/memory_augmented_agent_with_mem0_mongodb.ipynb) | Memory-augmented agent using Mem0 library with MongoDB |
| **Memory Bank** | [`memory_bank/memory_augmented_agent_with_local_memory.ipynb`](memory_bank/memory_augmented_agent_with_local_memory.ipynb) | Memory-augmented agent with local memory implementation |
| **MemoRizz** | [`part1/memorizz/memagent_single_agent.ipynb`](memorizz/memagent_single_agent.ipynb) | Single agent memory implementation with MemoRizz framework |

## Purpose of This Repository

This repository demonstrates various approaches to implementing memory management in AI agents and agentic systems. It covers:

- **Different memory storage backends** (MongoDB, local storage)
- **Various memory management libraries** (LangMem, Mem0, custom implementations)
- **Information retrieval techniques** for memory-augmented systems
- **Practical implementations** of memory-enabled AI agents

Each notebook provides hands-on examples and code implementations that complement the theoretical concepts covered in the course, allowing learners to experiment with different memory management strategies in AI systems.

## Utilities

The `utilities/` directory contains helper functions including:
- `pdf_chunker.py` - Utilities for processing and chunking PDF documents for memory storage
