# TMX MapForge

Procedural map generation tool for [Rusted Warfare](https://store.steampowered.com/app/647960/Rusted_Warfare__RTS/), outputting industry-standard TMX (Tiled Map eXchange) format. Available as a desktop app (Python) and a web app (Rust/WASM + Next.js).

## Features

- **6-step wizard** for interactive map creation: coastline, walls, elevation, command centers, resources, export
- **Perlin noise terrain** with configurable elevation and ocean levels
- **Mirroring modes** — horizontal, vertical, diagonal, or both axes
- **Automatic placement** of command centers and resources with distance constraints
- **TMX export** with gzip-compressed tile data, terrain transitions, and decoration layers
- **Coastline smoothing** with configurable shore complexity

## Tech Stack

### Desktop
- **Python 3** — PyQt5 (GUI), NumPy, SciPy, Perlin-noise, Matplotlib, Pillow

### Web ([Live Demo](https://tmx-mapforge.vercel.app/))
- **Rust** compiled to WebAssembly (terrain generation, TMX encoding)
- **Next.js 16**, React 19, TypeScript, Tailwind CSS 4
- Static export deployed on Vercel

## Usage

### Web
Visit [tmx-mapforge.vercel.app](https://tmx-mapforge.vercel.app/) — no installation needed.

### Desktop
```bash
cd desktop
pip install -r requirements.txt
python wizard_gui.py
```

## Project Structure

```
├── desktop/          # Python desktop app (PyQt5 wizard)
├── web/
│   ├── rust-map-gen/ # Rust WASM backend (algorithms, TMX export)
│   └── src/          # Next.js frontend (React UI, canvas renderer)
```

## License

MIT
