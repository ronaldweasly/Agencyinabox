"use client"

import { useEffect, useState } from "react"
import { motion, useSpring, useTransform } from "framer-motion"

interface AnimatedCounterProps {
    value: number
    format?: "number" | "currency" | "percent"
    className?: string
    prefix?: string
    suffix?: string
}

export function AnimatedCounter({
    value,
    format = "number",
    className = "",
    prefix = "",
    suffix = "",
}: AnimatedCounterProps) {
    const [isMounted, setIsMounted] = useState(false)
    const spring = useSpring(0, { mass: 0.8, stiffness: 75, damping: 15 })
    const display = useTransform(spring, (current) => {
        let formatted = current.toFixed(format === "percent" ? 1 : 0)
        if (format === "number" || format === "currency") {
            formatted = Math.round(current).toLocaleString("en-US")
        }
        if (format === "currency") {
            formatted = "$" + formatted
        }
        return `${prefix}${formatted}${suffix}`
    })

    useEffect(() => {
        setIsMounted(true)
        spring.set(value)
    }, [spring, value])

    if (!isMounted) {
        return <span className={className}>{prefix}{(value).toLocaleString()}{suffix}</span>
    }

    return <motion.span className={className}>{display}</motion.span>
}
