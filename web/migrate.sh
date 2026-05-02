#!/bin/bash
cd /root/.openclaw/workspace/coding/projects/LangBot/web

# Find and replace next/navigation
find src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec sed -i \
  -e "s/import {.*useRouter.*} from 'next\/navigation'/import { useNavigate } from 'react-router-dom'/g" \
  -e "s/import {.*usePathname.*} from 'next\/navigation'/import { useLocation } from 'react-router-dom'/g" \
  -e "s/import {.*useSearchParams.*} from 'next\/navigation'/import { useSearchParams } from 'react-router-dom'/g" \
  -e "s/const router = useRouter()/const navigate = useNavigate()/g" \
  -e "s/router\.push(/navigate(/g" \
  -e "s/router\.replace(/navigate(/g" \
  -e "s/router\.back()/navigate(-1)/g" \
  -e "s/router\.refresh()/navigate(0)/g" \
  -e "s/const pathname = usePathname()/const location = useLocation();\n  const pathname = location.pathname;/g" \
  -e "s/usePathname()/useLocation().pathname/g" \
  {} +

# Note: useSearchParams returns a tuple in react-router-dom. This might need manual fix depending on usage.

# Replace next/link
find src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec sed -i \
  -e "s/import Link from 'next\/link'/import { Link } from 'react-router-dom'/g" \
  -e "s/<Link href=/<Link to=/g" \
  {} +

# Remove 'use client'
find src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec sed -i "s/'use client';//g" {} +
find src -type f \( -name "*.ts" -o -name "*.tsx" \) -exec sed -i 's/"use client";//g' {} +

