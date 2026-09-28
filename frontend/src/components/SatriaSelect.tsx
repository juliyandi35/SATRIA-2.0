import { Check, ChevronDown } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { createPortal } from 'react-dom'

export interface SatriaSelectOption {
  value: string
  label: string
  disabled?: boolean
}

interface MenuPosition {
  left: number
  top: number
  width: number
  maxHeight: number
  opensUp: boolean
}

export function SatriaSelect({
  value,
  options,
  onChange,
  ariaLabel,
  icon,
  className = '',
  disabled = false,
}: {
  value: string
  options: SatriaSelectOption[]
  onChange: (value: string) => void
  ariaLabel: string
  icon?: ReactNode
  className?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const [position, setPosition] = useState<MenuPosition>({ left: 0, top: 0, width: 220, maxHeight: 280, opensUp: false })
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const matchedIndex = options.findIndex((option) => option.value === value)
  const selectedIndex = matchedIndex === -1 ? 0 : matchedIndex
  const selected = matchedIndex === -1 ? undefined : options[matchedIndex]

  const updatePosition = () => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const width = Math.min(Math.max(rect.width, 220), window.innerWidth - 16)
    const estimatedHeight = Math.min(292, Math.max(82, options.length * 35 + 12))
    const spaceBelow = window.innerHeight - rect.bottom - 8
    const spaceAbove = rect.top - 8
    const opensUp = spaceBelow < Math.min(estimatedHeight, 190) && spaceAbove > spaceBelow
    const maxHeight = Math.max(82, Math.min(estimatedHeight, opensUp ? spaceAbove - 6 : spaceBelow - 6))
    const left = Math.min(Math.max(8, rect.left), Math.max(8, window.innerWidth - width - 8))
    const top = opensUp ? Math.max(8, rect.top - maxHeight - 6) : rect.bottom + 6
    setPosition({ left, top, width, maxHeight, opensUp })
  }

  const openMenu = () => {
    if (disabled) return
    updatePosition()
    setActiveIndex(selectedIndex)
    setOpen(true)
  }

  const choose = (index: number) => {
    const option = options[index]
    if (!option || option.disabled) return
    onChange(option.value)
    setOpen(false)
    triggerRef.current?.focus()
  }

  const move = (direction: 1 | -1) => {
    if (!options.length) return
    let next = activeIndex
    for (let step = 0; step < options.length; step += 1) {
      next = (next + direction + options.length) % options.length
      if (!options[next].disabled) break
    }
    setActiveIndex(next)
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!open) openMenu()
      else move(event.key === 'ArrowDown' ? 1 : -1)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (open) choose(activeIndex)
      else openMenu()
    } else if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    } else if (event.key === 'Home' && open) {
      event.preventDefault()
      setActiveIndex(0)
    } else if (event.key === 'End' && open) {
      event.preventDefault()
      setActiveIndex(options.length - 1)
    }
  }

  useLayoutEffect(() => {
    if (!open) return
    updatePosition()
    const activeOption = document.getElementById(`${menuId}-option-${activeIndex}`)
    activeOption?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex, menuId, open, options.length])

  useEffect(() => {
    if (!open) return
    const handlePointer = (event: PointerEvent) => {
      const target = event.target as Node
      if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target)) setOpen(false)
    }
    const reposition = () => updatePosition()
    const scrollOptions = { capture: true, passive: true } as const
    document.addEventListener('pointerdown', handlePointer)
    window.addEventListener('resize', reposition)
    window.addEventListener('scroll', reposition, scrollOptions)
    return () => {
      document.removeEventListener('pointerdown', handlePointer)
      window.removeEventListener('resize', reposition)
      window.removeEventListener('scroll', reposition, scrollOptions)
    }
  }, [open, options.length])

  return (
    <div className={`satria-select ${open ? 'open' : ''} ${className}`.trim()}>
      <button
        ref={triggerRef}
        type="button"
        className="satria-select-trigger"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-activedescendant={open ? `${menuId}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onClick={() => open ? setOpen(false) : openMenu()}
        onKeyDown={handleKeyDown}
      >
        {icon && <span className="satria-select-icon">{icon}</span>}
        <span className="satria-select-value">{selected?.label ?? (value || 'Pilih')}</span>
        <ChevronDown className="satria-select-chevron" size={15} />
      </button>
      {open && createPortal(
        <div
          ref={menuRef}
          id={menuId}
          role="listbox"
          aria-label={ariaLabel}
          className={`satria-select-menu ${position.opensUp ? 'opens-up' : ''}`}
          style={{ left: position.left, top: position.top, width: position.width, maxHeight: position.maxHeight }}
        >
          {options.map((option, index) => (
            <button
              key={option.value || '__all'}
              id={`${menuId}-option-${index}`}
              type="button"
              role="option"
              aria-selected={option.value === value}
              disabled={option.disabled}
              className={index === activeIndex ? 'active' : ''}
              onPointerEnter={() => setActiveIndex(index)}
              onClick={() => choose(index)}
            >
              <span>{option.label}</span>
              {option.value === value && <Check size={14} />}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  )
}
