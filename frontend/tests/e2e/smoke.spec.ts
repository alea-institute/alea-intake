import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { wageTheftVisualization } from '../../src/test/fixtures/showcase'

test('showcase story, views, accessibility and mobile layout', async ({ page }) => {
  await page.route('**/api/v1/**', async route => {
    const p = new URL(route.request().url()).pathname
    const bodies: Record<string,unknown> = {
      '/api/v1/auth/showcase-notice':{consent_text:'Allow AI processing',idle_ttl_seconds:3600,reference_model:'gpt-4.1-mini'},
      '/api/v1/auth/guest':{access_token:'guest'}, '/api/v1/consent/grant':{},
      '/api/v1/intake/':{id:1,session_id:2,party_id:3},
      '/api/v1/analysis/1/analyze':{run_id:4,status:'completed',is_reference_model:true},
      '/api/v1/analysis/1/results':{claims:[{id:1,claim_name:'Unpaid wages',folio_iri:'https://folio.openlegalstandard.org/wages'}],deadlines:[{event_text:'File claim',computed:true,computed_date:'2027-01-01',citation:'Statute',citation_url:'https://www.revisor.mn.gov/',counting_method:'30 days',as_of_date:'2026-11-08'},{event_text:'Demand letter window',computed:true,computed_date:'2026-07-01',citation:'Statute',citation_url:'https://www.revisor.mn.gov/',counting_method:'15 days',as_of_date:'2026-11-08'},{event_text:'Pay date in agreement',event_type:'contractual',computed_date:'2026-12-15'},{event_text:'Retaliation complaint',jurisdiction:'MN'}]},
      '/api/v1/analysis/1/visualization':wageTheftVisualization,
      '/api/v1/output/generate':{documents:[{id:5}]},'/api/v1/output/5':{markdown_content:'# Your memo'},
      '/api/v1/intake/1/end-session':{},
    }
    await route.fulfill({status:p in bodies?200:404,contentType:'application/json',body:JSON.stringify(bodies[p]||{})})
  })
  await page.routeWebSocket('**/api/ws/intake/2', ws=>{
    let authenticated=false
    ws.onMessage(raw=>{
      const m=JSON.parse(String(raw))
      if(!authenticated) {expect(m.type).toBe('auth');expect(m.token).toBe('guest');authenticated=true}
      else if(m.type==='text_message') {ws.send(JSON.stringify({type:'message_ack',client_id:m.client_id,message_id:1}));ws.send(JSON.stringify({type:'system_message',content:'Saved'}))}
    })
  })
  await page.setViewportSize({width:390,height:844})
  await page.goto('/')
  await expect(page.getByText('A FOLIO demonstration. Not legal advice.')).toBeVisible()
  await expect(page.getByLabel('Model', {exact:true})).toHaveValue('gpt-4.1-mini')
  await expect(page.getByRole('option', {name:'OpenAI', exact:true})).toHaveAttribute('value','openai')
  const upload = page.getByLabel('Upload a PDF')
  await upload.scrollIntoViewIfNeeded()
  const bannerBox = await page.getByRole('note').boundingBox()
  const uploadBox = await upload.boundingBox()
  expect(bannerBox!.y + bannerBox!.height <= uploadBox!.y || uploadBox!.y + uploadBox!.height <= bannerBox!.y).toBe(true)
  await page.getByLabel('API key',{exact:true}).fill('sk-showcase-browser-test')
  await page.getByLabel('Try an example').selectOption('wage-theft')
  await page.getByLabel('Allow AI processing').check()
  await page.getByText('Analyze my story',{exact:true}).click()
  await expect(page.getByRole('heading',{name:'Unpaid wages'})).toBeVisible()
  await expect(page.getByText('Landlord has refused', {exact:false})).toHaveCount(0)
  await expect(page.locator('.showcase-narrative').getByText('108 hours', {exact:true})).toBeVisible()
  for(const name of ['Your story','Graph','Matrix','Deadlines','Memo']) {
    await page.getByRole('button',{name,exact:true}).click()
    if(name==='Graph') {
      await expect(page.getByRole('checkbox', {name:'Text and table alternative'})).toBeChecked()
      await expect(page.getByRole('table')).toBeVisible()
    }
    expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    await page.screenshot({path:`test-results/showcase-${name.replaceAll(' ','-')}.png`,fullPage:true})
  }
  await page.setViewportSize({width:1280,height:900})
  for(const name of ['Your story','Graph','Matrix','Deadlines','Memo']) {
    await page.getByRole('button',{name,exact:true}).click()
    if(name==='Graph') {
      const alternative = page.getByRole('checkbox', {name:'Text and table alternative'})
      await alternative.uncheck()
      await expect(page.locator('.showcase-graph svg')).toBeVisible()
    }
    expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
    await page.screenshot({path:`test-results/showcase-desktop-${name.replaceAll(' ','-')}.png`,fullPage:true})
  }
  await page.getByRole('button',{name:'End session and erase',exact:true}).click()
  await page.getByRole('button',{name:'Erase this session',exact:true}).click()
  await expect(page.getByLabel('Your story',{exact:true})).toHaveValue('')
  for(const route of ['/login','/admin','/oauth/finish','/intake/1/output']) {
    await page.goto(route)
    await expect(page.getByText('A FOLIO demonstration. Not legal advice.')).toBeVisible()
    await expect(page.getByRole('link',{name:/sign in|admin/i})).toHaveCount(0)
  }
})
