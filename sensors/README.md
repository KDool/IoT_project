## 🛠 Build Code Guide (Setup Instructions)

This project uses the Contiki-NG framework managed in a separate repository to optimize storage.

**1. Prepare the working directory:**
Make sure you place both repositories side by side in the same directory:
\`\`\`bash
mkdir IoT_Workspace && cd IoT_Workspace
git clone https://github.com/contiki-ng/contiki-ng.git
git clone <link-to-group-project-repo>
\`\`\`

**2. Standard compilation:**
Navigate to the project directory and run the make command. The system will automatically find the framework at `../contiki-ng`:
\`\`\`bash
cd project
make TARGET=nrf52840 BOARD=dongle
\`\`\`

**3. Custom compilation (If you place the Contiki-NG directory elsewhere):**
If your contiki-ng directory is located at a different path, you can pass that path directly to the make command without editing the Makefile:
\`\`\`bash
make TARGET=nrf52840 BOARD=dongle CONTIKI=/absolute/path/to/contiki-ng
\`\`\`