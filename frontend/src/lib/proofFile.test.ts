import { describe, expect, it } from 'vitest'
import { MAX_PROOF_BYTES, formatFileSize, validateProofFile } from './proofFile'

const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 0]
const JPG = [0xff, 0xd8, 0xff, 0xe0, 0, 0, 0, 0]
const PDF = [0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34]
const file = (bytes: number[], name: string) => new File([new Uint8Array(bytes)], name)

describe('validateProofFile', () => {
  it.each([[PNG, 'foto.png'], [JPG, 'foto.jpg'], [JPG, 'FOTO.JPEG'], [PDF, 'recibo.pdf']])('accepts a real %# file named %s', async (bytes, name) => {
    expect(await validateProofFile(file(bytes, name))).toBeNull()
  })

  it.each(['virus.exe', 'pagina.html', 'imagen.svg', 'sin-extension', 'doc.docx', 'x.png.exe'])('refuses the format of %s', async (name) => {
    expect(await validateProofFile(file(PNG, name))).toMatch(/Formato no admitido/)
  })

  it.each([
    [[0x4d, 0x5a, 0x90, 0, 0, 0, 0, 0], 'foto.png'], // an executable pretending to be a picture
    [[0x3c, 0x73, 0x63, 0x72, 0x69, 0x70, 0x74], 'foto.jpg'], // "<script"
    [PNG, 'recibo.pdf'],
    [PDF, 'foto.png'],
  ])('refuses content that does not match the name (%#)', async (bytes, name) => {
    expect(await validateProofFile(file(bytes, name))).toMatch(/no coincide/)
  })

  it('refuses an empty file', async () => {
    expect(await validateProofFile(file([], 'vacio.png'))).toMatch(/vacío/)
  })

  it('refuses a file over the limit and accepts one exactly at it', async () => {
    const big = new File([new Uint8Array(MAX_PROOF_BYTES + 1)], 'grande.png')
    const exact = new File([new Uint8Array([...PNG, ...new Array(MAX_PROOF_BYTES - PNG.length).fill(0)])], 'justo.png')

    expect(await validateProofFile(big)).toMatch(/demasiado grande/)
    expect(await validateProofFile(exact)).toBeNull()
  })
})

describe('formatFileSize', () => {
  it('writes sizes a person can read', () => {
    expect(formatFileSize(512)).toBe('512 B')
    expect(formatFileSize(2048)).toBe('2 KB')
    expect(formatFileSize(2.5 * 1024 * 1024)).toBe('2.5 MB')
  })
})
