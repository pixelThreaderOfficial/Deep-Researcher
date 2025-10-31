"""
FLOW

User Query -> analyze that text for sexual content -> IF sexual content then return "Sorry, I can't help with that."
-> If not sexual content then proceed to the research process.

5. Research process ->
    a. Web Search about that content
    a. Get the relevant information from the database using RAG.
    b. If relevant information is found, return the information.
    c. If relevant information is not found, proceed to the next step.
    d. Next step ->
        i. If the user query is not clear, return "I'm not sure what you mean. Please try again."
"""