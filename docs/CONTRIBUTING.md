# **Contributing** 🤝

We welcome contributions from the community! Every contribution, no matter how small, is appreciated and credited. Here’s how you can get involved:

## **How to contribute** 🛠️

1. **Fork the repository:** Start by forking the [CubeXpress](https://github.com/JulioContrerasH/CubeXpress) repository to your GitHub account. 🍴
2. **Clone your fork locally:**
    ```bash
    cd <directory_in_which_repo_should_be_created>
    git clone https://github.com/JulioContrerasH/CubeXpress.git
    cd cubexpress
    ```
3. **Create a branch:** Create a new branch for your feature or bug fix:
    ```bash
    git checkout -b name-of-your-bugfix-or-feature
    ```
4. **Set up the environment:** 🌱
   - If you're using `pyenv`, select a Python version:
     ```bash
     pyenv local <x.y.z>
     ```
   - Install dependencies and activate the environment:
     ```bash
     poetry install
     poetry shell
     ```
   - Install pre-commit hooks:
     ```bash
     poetry run pre-commit install
     ```
5. **Make your changes:** 🖋️ Develop your feature or fix, ensuring you write clear, concise commit messages and include any necessary tests.
6. **Check your changes:** ✅
   - Run formatting checks:
     ```bash
     make check
     ```
   - Run unit tests:
     ```bash
     make test
     ```
   - Optionally, run tests across different Python versions using tox:
     ```bash
     tox
     ```
7. **Submit a pull request:** 🚀 Push your branch to GitHub and submit a pull request to the `develop` branch of the CubeXpress repository. Ensure your pull request meets these guidelines:
   - Include tests.
   - Update the documentation if your pull request adds functionality.
   - Provide a detailed description of your changes.

## **Types of contributions** 📦

- **Report bugs:** 🐛
  - Report bugs by creating an issue on the [CubeXpress GitHub repository](https://github.com/JulioContrerasH/CubeXpress/issues). Please include your operating system, setup details, and steps to reproduce the bug.
- **Fix bugs:** 🛠️ Look for issues tagged with "bug" and "help wanted" in the repository to start fixing.
- **Implement features:** ✨ Contribute by implementing features tagged with "enhancement" and "help wanted."
- **Write documentation:** 📚 Contribute to the documentation in the official docs, docstrings, or through blog posts and articles.
- **Submit feedback:** 💬 Propose new features or give feedback by filing an issue on GitHub. 
  - Use the [CubeXpress GitHub issues page](https://github.com/JulioContrerasH/CubeXpress/issues) for feedback.