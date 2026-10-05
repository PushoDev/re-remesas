import { Eye, EyeOff } from 'lucide-react'
import { useState, type ComponentProps } from 'react'
import { inputClass } from '../lib/formStyles'

/** Password field with a show/hide toggle. Works with react-hook-form's register(). */
export default function PasswordInput(props: Omit<ComponentProps<'input'>, 'type'>) {
  const [visible, setVisible] = useState(false)

  return (
    <div className="relative">
      <input {...props} type={visible ? 'text' : 'password'} className={`${inputClass} pr-11`} />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
        aria-pressed={visible}
        className="absolute inset-y-0 right-0 mt-1 flex w-11 items-center justify-center rounded-r-lg text-slate-500 hover:text-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
      >
        {visible ? <EyeOff className="size-5" aria-hidden /> : <Eye className="size-5" aria-hidden />}
      </button>
    </div>
  )
}
