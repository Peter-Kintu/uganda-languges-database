/**
 * This file is part of django-tailwind and will be overridden every time you run
 * `python manage.py tailwind init`
 */

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './static/css/**/*.css',
    '../../templates/**/*.html',
    '../../**/templates/**/*.html',
    '../../static/js/**/*.js',
    '../../static/css/**/*.css',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}