/**
 * Early feedback for the proof file. The server repeats every one of these checks (and is the one
 * that decides), but telling the customer before the upload saves a round trip and a big transfer.
 */
export const MAX_PROOF_BYTES = 5 * 1024 * 1024
export const ACCEPTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.pdf'] as const

/** What a real file of each kind starts with. */
const SIGNATURES: Record<string, number[][]> = {
  '.jpg': [[0xff, 0xd8, 0xff]],
  '.jpeg': [[0xff, 0xd8, 0xff]],
  '.png': [[0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]],
  '.pdf': [[0x25, 0x50, 0x44, 0x46, 0x2d]], // %PDF-
}

function extensionOf(name: string): string {
  const dot = name.lastIndexOf('.')
  return dot === -1 ? '' : name.slice(dot).toLowerCase()
}

/** null when the file looks fine, otherwise what to tell the customer. Checks name, size and real content. */
export async function validateProofFile(file: File): Promise<string | null> {
  const extension = extensionOf(file.name)
  if (!(ACCEPTED_EXTENSIONS as readonly string[]).includes(extension)) {
    return 'Formato no admitido. Sube una imagen JPG o PNG, o un PDF.'
  }
  if (file.size === 0) return 'El archivo está vacío.'
  if (file.size > MAX_PROOF_BYTES) {
    return `El archivo es demasiado grande (máximo ${MAX_PROOF_BYTES / (1024 * 1024)} MB).`
  }

  const head = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  const matches = SIGNATURES[extension].some((signature) => signature.every((byte, index) => head[index] === byte))
  return matches ? null : 'El contenido no coincide con el tipo de archivo.'
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
